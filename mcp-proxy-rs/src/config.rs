//! Configuration loading and management for MCP Proxy

use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::path::Path;
use tracing::{debug, info, warn};

use crate::error::{Error, Result};

/// Settings for the MCP server
#[derive(Debug, Clone)]
pub struct McpServerSettings {
    /// Host address to bind to
    pub bind_host: String,
    /// Port to listen on
    pub port: u16,
    /// Whether to run in stateless mode
    pub stateless: bool,
    /// Allowed CORS origins
    pub allow_origins: Option<Vec<String>>,
    /// Log level
    pub log_level: LogLevel,
}

impl Default for McpServerSettings {
    fn default() -> Self {
        Self {
            bind_host: "127.0.0.1".to_string(),
            port: 8080,
            stateless: false,
            allow_origins: None,
            log_level: LogLevel::Info,
        }
    }
}

/// Log level configuration
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default)]
pub enum LogLevel {
    Debug,
    #[default]
    Info,
    Warning,
    Error,
    Critical,
}

impl LogLevel {
    pub fn as_str(&self) -> &'static str {
        match self {
            LogLevel::Debug => "debug",
            LogLevel::Info => "info",
            LogLevel::Warning => "warn",
            LogLevel::Error => "error",
            LogLevel::Critical => "error",
        }
    }
}

impl std::str::FromStr for LogLevel {
    type Err = Error;

    fn from_str(s: &str) -> Result<Self> {
        match s.to_lowercase().as_str() {
            "debug" => Ok(LogLevel::Debug),
            "info" => Ok(LogLevel::Info),
            "warning" | "warn" => Ok(LogLevel::Warning),
            "error" => Ok(LogLevel::Error),
            "critical" => Ok(LogLevel::Critical),
            _ => Err(Error::InvalidConfig(format!("Unknown log level: {}", s))),
        }
    }
}

/// Configuration for a single MCP server (from JSON config file)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ServerConfig {
    /// Command to execute
    pub command: String,
    /// Arguments to pass to the command
    #[serde(default)]
    pub args: Vec<String>,
    /// Environment variables
    #[serde(default)]
    pub env: HashMap<String, String>,
    /// Whether this server is enabled
    #[serde(default = "default_enabled")]
    pub enabled: bool,
}

fn default_enabled() -> bool {
    true
}

/// Top-level configuration file structure
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConfigFile {
    /// Map of server name to configuration
    #[serde(rename = "mcpServers")]
    pub mcp_servers: HashMap<String, ServerConfig>,
}

/// Named server configuration with resolved parameters
#[derive(Debug, Clone)]
pub struct NamedServerConfig {
    /// Server name
    pub name: String,
    /// Command to execute
    pub command: String,
    /// Arguments to pass to the command
    pub args: Vec<String>,
    /// Environment variables
    pub env: HashMap<String, String>,
    /// Working directory
    pub cwd: Option<String>,
}

/// Load named server configurations from a JSON file
pub fn load_named_server_configs_from_file(
    config_file_path: &Path,
    base_env: &HashMap<String, String>,
) -> Result<HashMap<String, NamedServerConfig>> {
    info!("Loading named server configurations from: {:?}", config_file_path);

    let content = std::fs::read_to_string(config_file_path).map_err(|e| {
        if e.kind() == std::io::ErrorKind::NotFound {
            Error::ConfigNotFound(config_file_path.display().to_string())
        } else {
            Error::IoError(e)
        }
    })?;

    let config_data: ConfigFile = serde_json::from_str(&content)?;

    let mut named_configs = HashMap::new();

    for (name, server_config) in config_data.mcp_servers {
        if !server_config.enabled {
            info!("Named server '{}' from config is not enabled. Skipping.", name);
            continue;
        }

        if server_config.command.is_empty() {
            warn!(
                "Named server '{}' from config is missing 'command'. Skipping.",
                name
            );
            continue;
        }

        // Merge base environment with server-specific environment
        let mut merged_env = base_env.clone();
        merged_env.extend(server_config.env);

        let named_config = NamedServerConfig {
            name: name.clone(),
            command: server_config.command.clone(),
            args: server_config.args,
            env: merged_env,
            cwd: None,
        };

        info!(
            "Configured named server '{}' from config: {} {}",
            name,
            server_config.command,
            named_config.args.join(" ")
        );

        named_configs.insert(name, named_config);
    }

    debug!("Loaded {} named server configurations", named_configs.len());
    Ok(named_configs)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;
    use tempfile::NamedTempFile;

    #[test]
    fn test_parse_config_file() {
        let config_json = r#"{
            "mcpServers": {
                "weather": {
                    "command": "python",
                    "args": ["weather.py", "--port", "8123"],
                    "env": {"API_KEY": "test123"}
                },
                "disabled_server": {
                    "command": "node",
                    "args": ["server.js"],
                    "enabled": false
                }
            }
        }"#;

        let mut temp_file = NamedTempFile::new().unwrap();
        temp_file.write_all(config_json.as_bytes()).unwrap();

        let base_env = HashMap::new();
        let configs = load_named_server_configs_from_file(temp_file.path(), &base_env).unwrap();

        assert_eq!(configs.len(), 1);
        assert!(configs.contains_key("weather"));
        assert!(!configs.contains_key("disabled_server"));

        let weather = configs.get("weather").unwrap();
        assert_eq!(weather.command, "python");
        assert_eq!(weather.args, vec!["weather.py", "--port", "8123"]);
        assert_eq!(weather.env.get("API_KEY"), Some(&"test123".to_string()));
    }

    #[test]
    fn test_log_level_parsing() {
        assert_eq!("debug".parse::<LogLevel>().unwrap(), LogLevel::Debug);
        assert_eq!("INFO".parse::<LogLevel>().unwrap(), LogLevel::Info);
        assert_eq!("Warning".parse::<LogLevel>().unwrap(), LogLevel::Warning);
        assert!("invalid".parse::<LogLevel>().is_err());
    }
}
