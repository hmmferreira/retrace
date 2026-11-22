use strict;
use warnings;
my ($root,$exporter)=@ARGV;
my $auth="$root/apple-private-apis/icloud-auth/src/client.rs";
my $main="$exporter/src/main.rs";
sub edit {
 my ($path,$old,$new)=@_;
 open my $f,'<',$path or die "cannot read source\n"; local $/; my $s=<$f>; close $f;
 my $n=($s =~ s/\Q$old\E/$new/g);
 die "expected one source match in $path\n" unless $n==1;
 open my $out,'>',$path or die "cannot write source\n"; print {$out} $s; close $out;
}
edit($auth, 'pub struct FetchedToken {', '#[derive(Clone, Serialize, Deserialize)]
pub struct FetchedToken {');
edit($auth, 'pub struct AppleAccount<T: AnisetteProvider> {', '
#[derive(Clone, Serialize, Deserialize)]
struct DragonSessionCache {
    #[serde(skip_serializing_if = "Option::is_none")]
    spd: Option<plist::Dictionary>,
    #[serde(skip_serializing_if = "Option::is_none")]
    username: Option<String>,
    tokens: HashMap<String, FetchedToken>,
}

pub struct AppleAccount<T: AnisetteProvider> {');
edit($auth, '    pub fn get_pet(&self) -> Option<String> {', '
    pub fn save_dragon_session(&self, path: &std::path::Path)
        -> Result<(), Box<dyn std::error::Error>> {
        use std::os::unix::fs::{OpenOptionsExt, PermissionsExt};
        let cache = DragonSessionCache {
            spd: self.spd.clone(),
            username: self.username.clone(),
            tokens: self.tokens.clone(),
        };
        let temp = path.with_extension("tmp");
        let file = std::fs::OpenOptions::new().write(true).create(true).truncate(true)
            .mode(0o600).open(&temp)?;
        file.set_permissions(std::fs::Permissions::from_mode(0o600))?;
        plist::to_writer_xml(file, &cache)?;
        std::fs::rename(temp, path)?;
        Ok(())
    }

    pub fn restore_dragon_session(path: &std::path::Path, client_info: LoginClientInfo,
        anisette: ArcAnisetteClient<T>) -> Result<Self, Box<dyn std::error::Error>> {
        use std::os::unix::fs::PermissionsExt;
        if std::fs::metadata(path)?.permissions().mode() & 0o077 != 0 {
            return Err("Session cache must have permission 600".into());
        }
        let cache: DragonSessionCache = plist::from_file(path)?;
        let mut account = Self::new_with_anisette(client_info, anisette)?;
        account.spd = cache.spd;
        account.username = cache.username;
        account.tokens = cache.tokens;
        // No password or password hash is persisted. Expired sessions need user login.
        account.hashed_password = None;
        Ok(account)
    }

    pub fn get_pet(&self) -> Option<String> {');
edit($main, '// ── Main ────────────────────────────────────────────────────────────────', '
fn persistent_config(state_dir: &PathBuf) -> Result<FakeIOSConfig, Box<dyn std::error::Error>> {
    use std::os::unix::fs::{OpenOptionsExt, PermissionsExt};
    let path = state_dir.join("device-identity.plist");
    if path.exists() {
        let map: plist::Dictionary = plist::from_file(&path)?;
        return Ok(FakeIOSConfig {
            device_uuid: map.get("device_uuid").and_then(plist::Value::as_string)
                .ok_or("Invalid saved device identity")?.to_string(),
            serial: map.get("serial").and_then(plist::Value::as_string)
                .ok_or("Invalid saved device identity")?.to_string(),
            udid: map.get("udid").and_then(plist::Value::as_string)
                .ok_or("Invalid saved device identity")?.to_string(),
        });
    }
    let config = FakeIOSConfig::new();
    let map = plist::Dictionary::from_iter([
        ("device_uuid".to_string(), plist::Value::String(config.device_uuid.clone())),
        ("serial".to_string(), plist::Value::String(config.serial.clone())),
        ("udid".to_string(), plist::Value::String(config.udid.clone())),
    ]);
    let file = std::fs::OpenOptions::new().write(true).create_new(true).mode(0o600).open(path)?;
    file.set_permissions(std::fs::Permissions::from_mode(0o600))?;
    plist::to_writer_xml(file, &map)?;
    Ok(config)
}

// ── Main ────────────────────────────────────────────────────────────────');
edit($main, '    let mut apple_id = String::new();', '    let mut cached_only = false;
    let mut login_only = false;
    let mut probe_services = false;
    let mut fresh_login = false;
    let mut apple_id = String::new();');
edit($main, '            "--apple-id" => {', '            "--cached-only" => { cached_only = true; }
            "--login-only" => { login_only = true; }
            "--probe-services" => { probe_services = true; }
            "--fresh-login" => { fresh_login = true; }
            "--apple-id" => {');
edit($main, '                eprintln!("Options:");', '                eprintln!("Options:");
                eprintln!("  --login-only       Save a private session and stop");
                eprintln!("  --cached-only      Refuse interactive login");
                eprintln!("  --probe-services   Read service metadata; no Keychain join");
                eprintln!("  --fresh-login      Replace session with interactive login");');
edit($main, '    if apple_id.is_empty() {', '    if apple_id.is_empty() && !cached_only && (fresh_login || !PathBuf::from("state/exporter-session.plist").exists()) {');
edit($main, '    eprint!("Password: ");
    let password = read_password();

', '');
edit($main, '    let config: Arc<dyn OSConfig> = Arc::new(FakeIOSConfig::new());', '    let config: Arc<dyn OSConfig> = Arc::new(persistent_config(&state_dir)?);');
edit($main, '    let apple_id_clone = apple_id.clone();
    let password_hash: Vec<u8> = Sha256::digest(password.as_bytes()).to_vec();
    let appleid_closure = move || (apple_id_clone.clone(), password_hash.clone());
    let tfa_closure = || {
        eprint!("2FA code: ");
        let mut input = String::new();
        std::io::stdin().read_line(&mut input).unwrap();
        input.trim().to_string()
    };

    let account = AppleAccount::login(
        appleid_closure,
        tfa_closure,
        login_info,
        anisette_client.clone(),
    )
    .await?;', '    let session_path = state_dir.join("exporter-session.plist");
    let account = if session_path.exists() && !fresh_login {
        eprintln!("  Reusing private session cache.");
        AppleAccount::restore_dragon_session(&session_path, login_info, anisette_client.clone())?
    } else {
        if cached_only {
            return Err("No session cache. Run export-airtags.sh --login-only interactively once.".into());
        }
        eprint!("Password: ");
        let password = read_password();
        let apple_id_clone = apple_id.clone();
        let password_hash: Vec<u8> = Sha256::digest(password.as_bytes()).to_vec();
        let appleid_closure = move || (apple_id_clone.clone(), password_hash.clone());
        let tfa_closure = || {
            eprint!("SMS 2FA code: ");
            read_password()
        };
        AppleAccount::login(appleid_closure, tfa_closure, login_info, anisette_client.clone()).await?
    };
    account.save_dragon_session(&session_path)?;
    eprintln!("  Session cached privately (600); no password/hash stored.");
    if login_only {
        eprintln!("Login-only complete; no Keychain recovery or export attempted.");
        return Ok(());
    }');
edit($main, '    eprintln!("  Logged in (dsid={})", dsid);', '    eprintln!("  Apple authentication ready.");');
edit($main, '    let mobileme = delegates.mobileme.expect("No MobileMe delegate returned");', '    let mobileme = delegates.mobileme.expect("No MobileMe delegate returned");
    if probe_services {
        use std::os::unix::fs::{OpenOptionsExt, PermissionsExt};
        let file = std::fs::OpenOptions::new().write(true).create(true).truncate(true)
            .mode(0o600).open(state_dir.join("service-metadata.plist"))?;
        file.set_permissions(std::fs::Permissions::from_mode(0o600))?;
        plist::to_writer_xml(file, &mobileme.config)?;
        eprintln!("Probe: MobileMe config entries: {}; escrow endpoint present: {}",
            mobileme.config.len(),
            KeychainClientState::new(dsid.clone(), adsid.clone(), &mobileme).is_some());
        eprintln!("Probe complete; no Keychain join or AirTag export attempted.");
        return Ok(());
    }
');
open my $out,'>>',$main or die "cannot append tests\n";
print {$out} '
#[cfg(test)]
mod dragon_session_tests {
    use super::*;
    use std::os::unix::fs::PermissionsExt;

    #[derive(serde::Serialize)]
    struct SyntheticToken {
        token: String,
        expiration: std::time::SystemTime,
    }

    #[tokio::test]
    async fn cache_round_trip_is_private_and_omits_password_hash() {
        let config = FakeIOSConfig::new();
        let login_info = config.get_gsa_config(&APSState::default(), false);
        let anisette = Arc::new(Mutex::new(AnisetteClient::new(
            RemoteAnisetteProviderV3::new(
                "http://example.invalid".into(), login_info.clone(), PathBuf::from("/tmp/unused")
            )
        )));
        let mut account = AppleAccount::new_with_anisette(login_info.clone(), anisette.clone()).unwrap();
        account.username = Some("test@example.invalid".into());
        account.spd = Some(plist::Dictionary::from_iter([
            ("data".to_string(), plist::Value::Data(vec![1, 2, 3]))
        ]));
        account.hashed_password = Some(vec![4, 5, 6]);
        let tokens = std::collections::HashMap::from([
            ("test".to_string(), SyntheticToken {
                token: "synthetic-token".into(),
                expiration: std::time::UNIX_EPOCH + std::time::Duration::from_secs(2000000000),
            })
        ]);
        let token_values = plist::to_value(&tokens).unwrap();
        account.tokens = plist::from_value(&token_values).unwrap();
        let path = std::env::temp_dir().join(format!("dragon-cache-{}.plist", uuid::Uuid::new_v4()));
        account.save_dragon_session(&path).unwrap();
        assert_eq!(std::fs::metadata(&path).unwrap().permissions().mode() & 0o777, 0o600);
        let restored = AppleAccount::restore_dragon_session(
            &path, login_info.clone(), anisette.clone()).unwrap();
        assert_eq!(restored.spd, account.spd);
        assert_eq!(plist::to_value(&restored.tokens).unwrap(), token_values);
        assert!(restored.hashed_password.is_none());
        assert!(!std::fs::read_to_string(&path).unwrap().contains("hashed_password"));
        std::fs::set_permissions(&path, std::fs::Permissions::from_mode(0o644)).unwrap();
        assert!(AppleAccount::restore_dragon_session(&path, login_info, anisette).is_err());
        std::fs::remove_file(path).unwrap();
    }

    #[test]
    fn identity_is_stable_across_process_runs() {
        let dir = std::env::temp_dir().join(format!("dragon-identity-{}", uuid::Uuid::new_v4()));
        std::fs::create_dir(&dir).unwrap();
        let first = persistent_config(&dir).unwrap();
        let second = persistent_config(&dir).unwrap();
        assert_eq!(first.device_uuid, second.device_uuid);
        assert_eq!(first.udid, second.udid);
        std::fs::remove_dir_all(dir).unwrap();
    }
}
';
close $out;

open my $cargo, '>>', "$exporter/Cargo.toml" or die "cannot add test dependency\n";
print {$cargo} '
[dev-dependencies]
serde = { version = "1", features = ["derive"] }
';
close $cargo;
