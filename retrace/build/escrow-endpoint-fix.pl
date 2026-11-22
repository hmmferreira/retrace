use strict;
use warnings;
my ($root, $exporter) = @ARGV;
die "source roots required\n" unless $root && $exporter;
sub edit {
 my ($path,$old,$new) = @_;
 open my $f, '<', $path or die "cannot read source\n"; local $/; my $s=<$f>; close $f;
 my $count=($s =~ s/\Q$old\E/$new/g);
 die "expected exactly one source match in $path\n" unless $count==1;
 open my $out,'>',$path or die "cannot write source\n"; print {$out} $s; close $out;
}
edit("$root/src/auth.rs", '    Ok(DelegateResponses {
        ids: get_delegate(delegates, "com.apple.private.ids")?,
        mobileme: get_delegate(delegates, "com.apple.mobileme")?,
    })', '    let mut mobileme: Option<MobileMeDelegateResponse> =
        get_delegate(delegates, "com.apple.mobileme")?;
    if let Some(mobileme) = &mut mobileme {
        mobileme.config = get_delegate(delegates, "com.apple.mobileme")?
            .expect("Missing MobileMe service data");
    }
    Ok(DelegateResponses {
        ids: get_delegate(delegates, "com.apple.private.ids")?,
        mobileme,
    })');
edit("$root/src/icloud/keychain.rs", '        let host = delegate.config.get("com.apple.Dataclass.KeychainSync")?.as_dictionary().unwrap().get("escrowProxyUrl")?.as_string().unwrap().to_string();', '        let config = Value::Dictionary(delegate.config.clone());
        let host = Self::find_escrow_proxy_url(&config)?.to_string();');
edit("$root/src/icloud/keychain.rs", 'impl KeychainClientState {', 'impl KeychainClientState {
    fn find_escrow_proxy_url(value: &Value) -> Option<&str> {
        match value {
            Value::Dictionary(dict) => {
                if let Some(url) = dict.get("escrowProxyUrl").and_then(Value::as_string) {
                    return Some(url);
                }
                dict.values().find_map(Self::find_escrow_proxy_url)
            }
            Value::Array(values) => values.iter().find_map(Self::find_escrow_proxy_url),
            _ => None,
        }
    }

    pub fn refresh_escrow_endpoint(&mut self, delegate: &MobileMeDelegateResponse) -> bool {
        let config = Value::Dictionary(delegate.config.clone());
        if let Some(host) = Self::find_escrow_proxy_url(&config) {
            self.host = host.to_string();
            true
        } else {
            false
        }
    }
');
edit("$exporter/src/main.rs", '    let keychain_state: KeychainClientState = if let Ok(state) =', '    let mut keychain_state: KeychainClientState = if let Ok(state) =');
edit("$exporter/src/main.rs", '    let account_arc = Arc::new(DebugMutex::new(account));', '    if !keychain_state.refresh_escrow_endpoint(&mobileme) {
        return Err("Apple did not supply an escrow endpoint. Stopped without using a guessed fallback.".into());
    }
    let backup = keychain_state_path.with_extension("pre-endpoint-fix.plist");
    if keychain_state_path.exists() && !backup.exists() {
        std::fs::copy(&keychain_state_path, &backup)?;
    }
    plist::to_file_xml(&keychain_state_path, &keychain_state)?;
    eprintln!("  Using escrow endpoint supplied by Apple.");

    let account_arc = Arc::new(DebugMutex::new(account));');
open my $test, '>>', "$root/src/icloud/keychain.rs" or die "cannot append tests\n";
print {$test} '
#[cfg(test)]
mod dragon_escrow_endpoint_tests {
    use super::*;

    #[test]
    fn finds_nested_apple_endpoint() {
        let config = Value::Dictionary(plist::Dictionary::from_iter([
            ("services".to_string(), Value::Array(vec![
                Value::Dictionary(plist::Dictionary::from_iter([
                    ("escrowProxyUrl".to_string(),
                     Value::String("https://example.invalid:443".to_string()))
                ]))
            ]))
        ]));
        assert_eq!(KeychainClientState::find_escrow_proxy_url(&config),
                   Some("https://example.invalid:443"));
    }

    #[test]
    fn refuses_missing_endpoint() {
        let config = Value::Dictionary(plist::Dictionary::new());
        assert_eq!(KeychainClientState::find_escrow_proxy_url(&config), None);
    }
}
';
close $test;
