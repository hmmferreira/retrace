use strict;
use warnings;
my ($root,$exporter)=@ARGV;
my $lib="$root/src/lib.rs";
my $auth="$root/src/auth.rs";
my $keychain="$root/src/icloud/keychain.rs";
my $main="$exporter/src/main.rs";
sub edit {
 my($path,$old,$new)=@_;
 open my $in,'<',$path or die "cannot read source\n";local $/;my $s=<$in>;close $in;
 my $n=($s =~ s/\Q$old\E/$new/g);die "expected one source match in $path\n" unless $n==1;
 open my $out,'>',$path or die "cannot write source\n";print {$out} $s;close $out;
}
edit($lib,'pub use auth::{request_update_account, UpdateAccountFinish};','pub use auth::MobileMeDelegateResponse;
pub use auth::{request_update_account, UpdateAccountFinish};');
edit($auth,'    pub async fn get_mme_token(&self, token: &str) -> Result<String, PushError> {','    pub async fn install_mme_cache(&self, delegate: MobileMeDelegateResponse) {
        *self.mme_delegate.lock().await = Some(delegate);
        *self.mme_refreshed.lock().await = SystemTime::now();
    }

    pub async fn get_mme_token(&self, token: &str) -> Result<String, PushError> {');
edit($main,'    let delegates =
        login_apple_delegates(&account, None, config.as_ref(), &[LoginDelegate::MobileMe]).await?;
    let mut mobileme = delegates.mobileme.expect("No MobileMe delegate returned");','    let service_cache_path = state_dir.join("service-metadata.plist");
    let mut mobileme: rustpush::MobileMeDelegateResponse =
        if service_cache_path.exists() && !fresh_login {
            let saved: plist::Dictionary = plist::from_file(&service_cache_path)?;
            let mut delegate: rustpush::MobileMeDelegateResponse =
                plist::from_value(&plist::Value::Dictionary(saved.clone()))?;
            delegate.config = saved;
            eprintln!("  Reusing cached MobileMe service tokens.");
            delegate
        } else {
            let delegates = login_apple_delegates(
                &account, None, config.as_ref(), &[LoginDelegate::MobileMe]).await?;
            delegates.mobileme.expect("No MobileMe delegate returned")
        };');
edit($main,'    let token_provider = TokenProvider::new(account_arc.clone(), config.clone());','    let token_provider = TokenProvider::new(account_arc.clone(), config.clone());
    token_provider.install_mme_cache(mobileme).await;');
edit($keychain,'    pub async fn get_viable_bottles(&self) -> Result<Vec<(EscrowData, EscrowMetadata)>, PushError> {','    pub async fn probe_recovery_device_count(&self) -> Result<usize, PushError> {
        let response: CuttlefishFetchViableBottleResponse = self.invoke_cuttlefish(
            "fetchViableBottles",
            CuttlefishFetchViableBottleRequest {
                filter: Some(1), metrics: Some(vec![])
            }
        ).await?;
        Ok(response.valid.len())
    }

    pub async fn get_viable_bottles(&self) -> Result<Vec<(EscrowData, EscrowMetadata)>, PushError> {');
edit($main,'        let bottles = keychain.get_viable_bottles().await?;
        eprintln!("Probe: usable recovery devices: {}", bottles.len());','        let count = keychain.probe_recovery_device_count().await?;
        eprintln!("Probe: current recovery devices: {}", count);');
