//! HTTP client wrapper with logging capabilities

use reqwest::{header::HeaderMap, Client, ClientBuilder};
use std::time::Duration;
use tracing::{debug, info};

use crate::error::Result;

/// Configuration for the HTTP client
#[derive(Debug, Clone)]
pub struct HttpClientConfig {
    /// Custom headers to include with all requests
    pub headers: Option<HeaderMap>,
    /// Request timeout in seconds
    pub timeout_secs: u64,
    /// Whether to verify SSL certificates
    pub verify_ssl: bool,
    /// Path to custom CA certificate bundle
    pub ca_cert_path: Option<String>,
}

impl Default for HttpClientConfig {
    fn default() -> Self {
        Self {
            headers: None,
            timeout_secs: 30,
            verify_ssl: true,
            ca_cert_path: None,
        }
    }
}

/// Create a configured HTTP client with logging capabilities
pub fn create_http_client(config: &HttpClientConfig) -> Result<Client> {
    let mut builder = ClientBuilder::new()
        .timeout(Duration::from_secs(config.timeout_secs))
        .redirect(reqwest::redirect::Policy::limited(10));

    // Configure SSL verification
    if !config.verify_ssl {
        debug!("SSL verification disabled");
        builder = builder.danger_accept_invalid_certs(true);
    }

    // Add custom CA certificate if provided
    if let Some(ref ca_path) = config.ca_cert_path {
        debug!("Using custom CA certificate bundle: {}", ca_path);
        let cert_data = std::fs::read(ca_path)?;
        let cert = reqwest::Certificate::from_pem(&cert_data)
            .map_err(|e| crate::error::Error::HttpError(e))?;
        builder = builder.add_root_certificate(cert);
    }

    // Add default headers if provided
    if let Some(ref headers) = config.headers {
        builder = builder.default_headers(headers.clone());
    }

    let client = builder.build()?;
    info!("HTTP client created with timeout={}s, verify_ssl={}",
          config.timeout_secs, config.verify_ssl);

    Ok(client)
}

/// Mask sensitive header values for logging
pub fn mask_sensitive_headers(headers: &HeaderMap) -> Vec<(String, String)> {
    const SENSITIVE_HEADERS: &[&str] = &["authorization", "x-api-key", "cookie", "x-access-token"];

    headers
        .iter()
        .map(|(key, value)| {
            let key_lower = key.as_str().to_lowercase();
            let value_str = if SENSITIVE_HEADERS.contains(&key_lower.as_str()) {
                "***MASKED***".to_string()
            } else {
                value.to_str().unwrap_or("<binary>").to_string()
            };
            (key.to_string(), value_str)
        })
        .collect()
}

/// Log an HTTP request
pub fn log_request(method: &str, url: &str, headers: &HeaderMap) {
    info!("HTTP Request: {} {}", method, url);
    debug!("Request Headers: {:?}", mask_sensitive_headers(headers));
}

/// Log an HTTP response
pub fn log_response(method: &str, url: &str, status: u16, reason: &str) {
    debug!("HTTP Response: {} {} - {} {}", method, url, status, reason);
}

#[cfg(test)]
mod tests {
    use super::*;
    use reqwest::header::{HeaderValue, AUTHORIZATION, CONTENT_TYPE};

    #[test]
    fn test_mask_sensitive_headers() {
        let mut headers = HeaderMap::new();
        headers.insert(AUTHORIZATION, HeaderValue::from_static("Bearer secret123"));
        headers.insert(CONTENT_TYPE, HeaderValue::from_static("application/json"));

        let masked = mask_sensitive_headers(&headers);

        let auth = masked.iter().find(|(k, _)| k == "authorization").unwrap();
        assert_eq!(auth.1, "***MASKED***");

        let content_type = masked.iter().find(|(k, _)| k == "content-type").unwrap();
        assert_eq!(content_type.1, "application/json");
    }

    #[test]
    fn test_default_config() {
        let config = HttpClientConfig::default();
        assert_eq!(config.timeout_secs, 30);
        assert!(config.verify_ssl);
        assert!(config.headers.is_none());
    }
}
