use strict;
use warnings;
my ($path)=@ARGV;
open my $in,'<',$path or die "cannot read exporter source\n";
local $/; my $source=<$in>; close $in;
my $old='let filename = format!("{}.plist", safe_name);';
my $new='let filename = accessory_export_filename(&safe_name, &acc.master_record.stable_identifier);';
my $count=($source =~ s/\Q$old\E/$new/g);
die "expected one filename match\n" unless $count==1;
my $marker='// ── Main ────────────────────────────────────────────────────────────────';
my $helper=q{
fn accessory_export_filename(name: &str, identifier: &str) -> String {
    let prefix: String = name.chars()
        .filter(|c| c.is_ascii_alphanumeric() || *c == '-' || *c == '_')
        .take(48).collect();
    let prefix = if prefix.is_empty() { "item" } else { &prefix };
    format!("{}--{:x}.plist", prefix, Sha256::digest(identifier.as_bytes()))
}

#[cfg(test)]
mod dragon_unique_export_tests {
    use super::accessory_export_filename;
    #[test]
    fn same_names_do_not_overwrite_different_items() {
        assert_ne!(accessory_export_filename("iPhone", "fixture-a"),
                   accessory_export_filename("iPhone", "fixture-b"));
    }
    #[test]
    fn names_are_stable_short_and_path_safe() {
        let long_name = "../".to_owned() + &"😀".repeat(200);
        let filename = accessory_export_filename(&long_name, "fixture-id");
        assert!(filename.starts_with("item--"));
        assert!(filename.len() <= 120);
        assert!(!filename.contains('/'));
        assert!(filename.ends_with(".plist"));
        assert_eq!(filename, accessory_export_filename(&long_name, "fixture-id"));
    }
}
};
$count=($source =~ s/\Q$marker\E/$helper\n$marker/);
die "expected main marker\n" unless $count==1;
open my $out,'>',$path or die "cannot write exporter source\n";
print {$out} $source; close $out;
