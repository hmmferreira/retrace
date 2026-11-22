use strict;
use warnings;
my $path=shift @ARGV;
open my $in,'<',$path or die "cannot read source\n";local $/;my $s=<$in>;close $in;
my $old='        keychain
            .join_clique_from_escrow(bottle, passcode.as_bytes(), b"findmy-export")';
my $new='        let private_escrow_password = private_exporter_escrow_password(&state_dir)?;
        keychain
            .join_clique_from_escrow(bottle, passcode.as_bytes(), private_escrow_password.as_bytes())';
my $n=($s =~ s/\Q$old\E/$new/g);die "expected one recovery password call\n" unless $n==1;
$s .= '
fn private_exporter_escrow_password(state_dir: &PathBuf)
    -> Result<String, Box<dyn std::error::Error>> {
    use std::os::unix::fs::{OpenOptionsExt, PermissionsExt};
    use std::io::Write;
    let path = state_dir.join("exporter-escrow-password");
    if path.exists() {
        if std::fs::metadata(&path)?.permissions().mode() & 0o077 != 0 {
            return Err("Exporter recovery password must have permission 600".into());
        }
        let password = std::fs::read_to_string(&path)?;
        if password.len() != 64 || !password.bytes().all(|c| c.is_ascii_hexdigit()) {
            return Err("Invalid saved exporter recovery password".into());
        }
        return Ok(password);
    }
    let bytes: [u8; 32] = rand::random();
    let password: String = bytes.iter().map(|byte| format!("{:02x}", byte)).collect();
    let mut file = std::fs::OpenOptions::new().write(true).create_new(true)
        .mode(0o600).open(path)?;
    file.set_permissions(std::fs::Permissions::from_mode(0o600))?;
    file.write_all(password.as_bytes())?;
    Ok(password)
}

#[cfg(test)]
mod dragon_escrow_password_tests {
    use super::*;
    use std::os::unix::fs::PermissionsExt;
    #[test]
    fn private_recovery_password_is_stable_and_owner_only() {
        let dir=std::env::temp_dir().join(format!("dragon-escrow-{}",uuid::Uuid::new_v4()));
        std::fs::create_dir(&dir).unwrap();
        let first=private_exporter_escrow_password(&dir).unwrap();
        let second=private_exporter_escrow_password(&dir).unwrap();
        assert_eq!(first,second);
        assert_eq!(first.len(),64);
        assert_ne!(first,"findmy-export");
        let path=dir.join("exporter-escrow-password");
        assert_eq!(std::fs::metadata(&path).unwrap().permissions().mode() & 0o777,0o600);
        std::fs::set_permissions(&path,std::fs::Permissions::from_mode(0o644)).unwrap();
        assert!(private_exporter_escrow_password(&dir).is_err());
        std::fs::remove_dir_all(dir).unwrap();
    }
}
';
open my $out,'>',$path or die "cannot write source\n";print {$out} $s;close $out;
