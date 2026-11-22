use strict;
use warnings;
my $path = shift @ARGV or die "source path required\n";
open my $in,'<',$path or die "cannot read source\n"; local $/; my $s=<$in>;close $in;
sub change {
 my ($old,$new)=@_;
 my $n=($s =~ s/\Q$old\E/$new/g); die "expected one source match\n" unless $n==1;
}
change('    let mut probe_services = false;','    let mut probe_services = false;
    let mut probe_escrow = false;');
change('            "--probe-services" => { probe_services = true; }','            "--probe-services" => { probe_services = true; }
            "--probe-escrow" => { probe_escrow = true; }');
change('                eprintln!("  --probe-services   Read service metadata; no Keychain join");','                eprintln!("  --probe-services   Read service metadata; no Keychain join");
                eprintln!("  --probe-escrow     List recovery-device count; no Keychain join");');
change('    let mobileme = delegates.mobileme.expect("No MobileMe delegate returned");','    let mut mobileme = delegates.mobileme.expect("No MobileMe delegate returned");
    if KeychainClientState::new(dsid.clone(), adsid.clone(), &mobileme).is_none() {
        let token = mobileme.tokens.get("mmeAuthToken")
            .ok_or("MobileMe did not supply its account-settings token")?;
        let headers = anisette_client.lock().await.get_headers().await?.clone();
        let mut request = reqwest::Client::new()
            .post("https://setup.icloud.com/setup/get_account_settings")
            .basic_auth(&dsid, Some(token))
            .header("X-Apple-ADSID", &adsid)
            .header("User-Agent", config.get_normal_ua("com.apple.iCloudHelper/282"))
            .header("X-Mme-Client-Info", config.get_mme_clientinfo("com.apple.AuthKit/1 (com.apple.akd/1.0)"))
            .header("Content-Type", "application/xml")
            .body(Vec::<u8>::new());
        for (key, value) in &headers {
            request = request.header(key.as_str(), value.as_str());
        }
        let response = request.send().await?;
        let status = response.status();
        let body = response.bytes().await?;
        if !status.is_success() {
            return Err(format!("Account service discovery HTTP {}", status.as_u16()).into());
        }
        let services: plist::Dictionary = plist::from_bytes(&body)?;
        mobileme.config.insert("account-services".to_string(),
            plist::Value::Dictionary(services));
        eprintln!("  Loaded account-specific Apple service map.");
    }
');
change('    if keychain.is_in_clique().await {','    if probe_escrow {
        let bottles = keychain.get_viable_bottles().await?;
        eprintln!("Probe: usable recovery devices: {}", bottles.len());
        eprintln!("Probe complete; no Keychain join or AirTag export attempted.");
        return Ok(());
    }
    if keychain.is_in_clique().await {');
open my $out,'>',$path or die "cannot write source\n";print {$out} $s;close $out;

my $cargo_path = $path;
$cargo_path =~ s@/src/main.rs$@/Cargo.toml@;
open my $cargo, '>>', $cargo_path or die "cannot add HTTP dependency\n";
print {$cargo} '
[dependencies.reqwest]
version = "0.11.27"
';
close $cargo;
