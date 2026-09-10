use ed25519_dalek::{Signature, VerifyingKey};
use serde::{Deserialize, Serialize};
use std::fs;
use std::io::{self, Read, Write};
use std::path::{Path, PathBuf};

const PROTOCOL_VERSION: u8 = 1;
const MAX_REQUEST_BYTES: usize = 512 * 1024;
const MAX_PAYLOAD_BYTES: usize = 64 * 1024;
const MAX_CATALOG_BYTES: usize = 32 * 1024;
const MAX_KEY_ID_BYTES: usize = 64;
const UPDATE_KEY_CATALOG_NAME: &str = "update-keys.json";

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct UpdateKeyCatalog {
    schema_version: u8,
    keys: Vec<UpdateKeyRecord>,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct UpdateKeyRecord {
    key_id: String,
    algorithm: String,
    public_key_hex: String,
    state: KeyState,
}

#[derive(Clone, Copy, Debug, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "lowercase")]
enum KeyState {
    Current,
    Next,
}

#[derive(Debug)]
struct ValidatedKey {
    key_id: String,
    verifying_key: VerifyingKey,
}

#[derive(Debug)]
struct ValidatedCatalog {
    keys: Vec<ValidatedKey>,
}

#[derive(Debug, Deserialize)]
#[serde(deny_unknown_fields)]
struct VerifyRequest {
    protocol_version: u8,
    key_id: String,
    algorithm: String,
    payload: Vec<u8>,
    signature: Vec<u8>,
}

#[derive(Serialize)]
struct VerifyResponse {
    protocol_version: u8,
    verified: bool,
}

fn valid_key_id(value: &str) -> bool {
    !value.is_empty()
        && value.len() <= MAX_KEY_ID_BYTES
        && value
            .bytes()
            .all(|byte| byte.is_ascii_lowercase() || byte.is_ascii_digit() || b"._-".contains(&byte))
}

fn hex_nibble(byte: u8) -> Option<u8> {
    match byte {
        b'0'..=b'9' => Some(byte - b'0'),
        b'a'..=b'f' => Some(byte - b'a' + 10),
        _ => None,
    }
}

fn decode_lower_hex<const N: usize>(value: &str) -> Option<[u8; N]> {
    if value.len() != N * 2 {
        return None;
    }
    let encoded = value.as_bytes();
    let mut output = [0_u8; N];
    for (index, byte) in output.iter_mut().enumerate() {
        let high = hex_nibble(encoded[index * 2])?;
        let low = hex_nibble(encoded[index * 2 + 1])?;
        *byte = (high << 4) | low;
    }
    Some(output)
}

fn parse_catalog(bytes: &[u8]) -> Option<ValidatedCatalog> {
    if bytes.is_empty() || bytes.len() > MAX_CATALOG_BYTES {
        return None;
    }
    let document: UpdateKeyCatalog = serde_json::from_slice(bytes).ok()?;
    if document.schema_version != 1 || document.keys.is_empty() || document.keys.len() > 2 {
        return None;
    }

    let current_count = document
        .keys
        .iter()
        .filter(|record| record.state == KeyState::Current)
        .count();
    if current_count != 1 {
        return None;
    }

    let mut keys: Vec<ValidatedKey> = Vec::with_capacity(document.keys.len());
    for record in document.keys {
        if !valid_key_id(&record.key_id) || record.algorithm != "ed25519" {
            return None;
        }
        if keys.iter().any(|existing| existing.key_id == record.key_id) {
            return None;
        }
        let key_bytes = decode_lower_hex::<32>(&record.public_key_hex)?;
        if keys
            .iter()
            .any(|existing| existing.verifying_key.to_bytes() == key_bytes)
        {
            return None;
        }
        let verifying_key = VerifyingKey::from_bytes(&key_bytes).ok()?;
        keys.push(ValidatedKey {
            key_id: record.key_id,
            verifying_key,
        });
    }
    Some(ValidatedCatalog { keys })
}

fn read_bounded_file(path: &Path, max_bytes: usize) -> Option<Vec<u8>> {
    let metadata = fs::metadata(path).ok()?;
    if !metadata.is_file() || metadata.len() > max_bytes as u64 {
        return None;
    }
    let bytes = fs::read(path).ok()?;
    (bytes.len() <= max_bytes).then_some(bytes)
}

pub(crate) fn catalog_is_valid(path: &Path) -> bool {
    read_bounded_file(path, MAX_CATALOG_BYTES)
        .and_then(|bytes| parse_catalog(&bytes))
        .is_some()
}

pub(crate) fn catalog_path_for_executable(executable: &Path) -> Option<PathBuf> {
    #[cfg(target_os = "windows")]
    {
        return Some(executable.parent()?.join(UPDATE_KEY_CATALOG_NAME));
    }
    #[cfg(target_os = "macos")]
    {
        return Some(
            executable
                .parent()?
                .parent()?
                .join("Resources")
                .join(UPDATE_KEY_CATALOG_NAME),
        );
    }
    #[cfg(not(any(target_os = "windows", target_os = "macos")))]
    {
        let _ = executable;
        None
    }
}

fn verify_request(catalog: &ValidatedCatalog, request: &VerifyRequest) -> bool {
    if request.protocol_version != PROTOCOL_VERSION
        || request.algorithm != "ed25519"
        || !valid_key_id(&request.key_id)
        || request.payload.len() > MAX_PAYLOAD_BYTES
        || request.signature.len() != 64
    {
        return false;
    }
    let Some(key) = catalog
        .keys
        .iter()
        .find(|key| key.key_id == request.key_id)
    else {
        return false;
    };
    let Ok(signature) = Signature::try_from(request.signature.as_slice()) else {
        return false;
    };
    key.verifying_key
        .verify_strict(&request.payload, &signature)
        .is_ok()
}

fn load_production_catalog() -> Option<ValidatedCatalog> {
    let executable = std::env::current_exe().ok()?;
    let path = catalog_path_for_executable(&executable)?;
    let bytes = read_bounded_file(&path, MAX_CATALOG_BYTES)?;
    parse_catalog(&bytes)
}

pub(crate) fn run_cli() -> i32 {
    let Some(catalog) = load_production_catalog() else {
        return 2;
    };

    let mut request_bytes = Vec::new();
    let read_result = io::stdin()
        .lock()
        .take((MAX_REQUEST_BYTES + 1) as u64)
        .read_to_end(&mut request_bytes);
    if read_result.is_err() || request_bytes.len() > MAX_REQUEST_BYTES {
        return 2;
    }
    let Ok(request) = serde_json::from_slice::<VerifyRequest>(&request_bytes) else {
        return 2;
    };

    let response = VerifyResponse {
        protocol_version: PROTOCOL_VERSION,
        verified: verify_request(&catalog, &request),
    };
    let stdout = io::stdout();
    let mut locked = stdout.lock();
    if serde_json::to_writer(&mut locked, &response).is_err() || writeln!(locked).is_err() {
        return 2;
    }
    0
}

#[cfg(test)]
mod tests {
    use super::*;

    const RFC8032_PUBLIC_KEY: &str =
        "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a";
    const RFC8032_SIGNATURE: &str = concat!(
        "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e06522490155",
        "5fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b"
    );

    fn catalog_json(state: &str, key_id: &str, key: &str) -> Vec<u8> {
        format!(
            r#"{{"schema_version":1,"keys":[{{"key_id":"{key_id}","algorithm":"ed25519","public_key_hex":"{key}","state":"{state}"}}]}}"#
        )
        .into_bytes()
    }

    fn rfc_catalog() -> ValidatedCatalog {
        parse_catalog(&catalog_json("current", "release-test", RFC8032_PUBLIC_KEY))
            .expect("RFC public test key should form a valid catalog")
    }

    fn rfc_request() -> VerifyRequest {
        VerifyRequest {
            protocol_version: 1,
            key_id: "release-test".to_string(),
            algorithm: "ed25519".to_string(),
            payload: Vec::new(),
            signature: decode_lower_hex::<64>(RFC8032_SIGNATURE)
                .expect("RFC signature hex")
                .to_vec(),
        }
    }

    #[test]
    fn verifies_rfc8032_public_test_vector_strictly() {
        assert!(verify_request(&rfc_catalog(), &rfc_request()));
    }

    #[test]
    fn rejects_mutated_payload_and_unknown_key() {
        let catalog = rfc_catalog();
        let mut request = rfc_request();
        request.payload.push(1);
        assert!(!verify_request(&catalog, &request));

        let mut request = rfc_request();
        request.key_id = "other-key".to_string();
        assert!(!verify_request(&catalog, &request));
    }

    #[test]
    fn catalog_requires_one_current_key_and_strict_lower_hex() {
        assert!(parse_catalog(&catalog_json("next", "release-test", RFC8032_PUBLIC_KEY)).is_none());
        assert!(parse_catalog(&catalog_json("current", "release-test", &RFC8032_PUBLIC_KEY.to_uppercase())).is_none());
        assert!(parse_catalog(&catalog_json("current", "Bad Key", RFC8032_PUBLIC_KEY)).is_none());
    }

    #[test]
    fn catalog_rejects_duplicate_key_ids_and_unknown_fields() {
        let duplicate = format!(
            r#"{{"schema_version":1,"keys":[{{"key_id":"release-test","algorithm":"ed25519","public_key_hex":"{RFC8032_PUBLIC_KEY}","state":"current"}},{{"key_id":"release-test","algorithm":"ed25519","public_key_hex":"0000000000000000000000000000000000000000000000000000000000000001","state":"next"}}]}}"#
        );
        assert!(parse_catalog(duplicate.as_bytes()).is_none());

        let unknown = format!(
            r#"{{"schema_version":1,"extra":true,"keys":[{{"key_id":"release-test","algorithm":"ed25519","public_key_hex":"{RFC8032_PUBLIC_KEY}","state":"current"}}]}}"#
        );
        assert!(parse_catalog(unknown.as_bytes()).is_none());
    }
}
