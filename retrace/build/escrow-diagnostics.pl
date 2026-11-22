use strict;
use warnings;
my $path = shift @ARGV or die "source path required\n";
open my $input, '<', $path or die "cannot read source\n";
local $/;
my $source = <$input>;
close $input;
my $old = '        if !resp.status().is_success() {
            return Err(PushError::EscrowError(plist::from_bytes(&resp.bytes().await?)?))
        }

        Ok(plist::from_bytes(&resp.bytes().await?)?)';
my $new = '        let status = resp.status();
        let body = resp.bytes().await?;
        if !status.is_success() || body.is_empty() {
            return Err(PushError::EscrowError(plist::Value::String(format!(
                "Escrow service HTTP {} returned {} bytes. Recovery records could not be read.",
                status.as_u16(), body.len()
            ))));
        }
        plist::from_bytes(&body).map_err(|_| PushError::EscrowError(
            plist::Value::String(format!(
                "Escrow service HTTP {} returned {} bytes that were not a valid plist.",
                status.as_u16(), body.len()
            ))
        ))';
my $count = ($source =~ s/\Q$old\E/$new/g);
die "expected exactly one escrow response handler\n" unless $count == 1;
open my $output, '>', $path or die "cannot write source\n";
print {$output} $source;
close $output;
