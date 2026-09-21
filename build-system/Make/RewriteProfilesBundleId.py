import os
import sys
import glob
import base64
import plistlib
import argparse
import tempfile
import subprocess


def run(args, input=None):
    proc = subprocess.run(args, input=input, capture_output=True)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr.decode(errors='replace'))
        raise SystemExit('Command failed: {}'.format(' '.join(args)))
    return proc.stdout


def run_pkcs12(base_args, input=None):
    # Some openssl builds (LibreSSL on macOS's system /usr/bin/openssl) don't
    # know -legacy; others (OpenSSL 3.x) need it to read older-style p12
    # files. Try without it first, then fall back to adding it.
    proc = subprocess.run(base_args, input=input, capture_output=True)
    if proc.returncode == 0:
        return proc.stdout
    proc2 = subprocess.run(base_args + ['-legacy'], input=input, capture_output=True)
    if proc2.returncode == 0:
        return proc2.stdout
    sys.stderr.write(proc.stderr.decode(errors='replace'))
    sys.stderr.write(proc2.stderr.decode(errors='replace'))
    raise SystemExit('Command failed: {}'.format(' '.join(base_args)))


def deep_replace(value, old, new):
    if isinstance(value, str):
        return value.replace(old, new)
    if isinstance(value, list):
        return [deep_replace(item, old, new) for item in value]
    if isinstance(value, dict):
        return {key: deep_replace(item, old, new) for key, item in value.items()}
    return value


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--profilesPath', required=True)
    parser.add_argument('--certsPath', required=True)
    parser.add_argument('--keychainName', required=True)
    parser.add_argument('--keychainPassword', required=True)
    parser.add_argument('--oldBundleId', required=True)
    parser.add_argument('--newBundleId', required=True)
    args = parser.parse_args()

    p12_path = os.path.join(args.certsPath, 'SelfSigned.p12')
    if not os.path.exists(p12_path):
        print('{} does not exist'.format(p12_path))
        sys.exit(1)

    cert_pem = run_pkcs12(['openssl', 'pkcs12', '-in', p12_path, '-passin', 'pass:', '-nokeys'])
    cert_der = run(['openssl', 'x509', '-outform', 'DER'], input=cert_pem)
    subject = run(['openssl', 'x509', '-noout', '-subject', '-nameopt', 'oneline,-esc_msb'], input=cert_pem).decode('utf-8')
    if 'CN = ' not in subject:
        print('Could not determine signing identity from {}'.format(p12_path))
        sys.exit(1)
    identity = subject.split('CN = ')[-1].split(',')[0].strip()
    print('Using signing identity: {}'.format(identity))

    profiles = glob.glob(os.path.join(args.profilesPath, '*.mobileprovision'))
    if not profiles:
        print('No .mobileprovision files found in {}'.format(args.profilesPath))
        sys.exit(1)

    for path in profiles:
        decoded = run(['security', 'cms', '-D', '-i', path])
        plist = plistlib.loads(decoded)

        plist = deep_replace(plist, args.oldBundleId, args.newBundleId)
        plist['DeveloperCertificates'] = [cert_der]
        plist.pop('DER-Encoded-Profile', None)

        tmp_in = tempfile.mktemp(suffix='.plist')
        with open(tmp_in, 'wb') as f:
            plistlib.dump(plist, f)

        try:
            run([
                'security', 'cms', '-S',
                '-k', args.keychainName,
                '-N', identity,
                '-i', tmp_in,
                '-o', path,
            ])
        finally:
            os.unlink(tmp_in)

        print('Rewrote {} -> application-identifier {}'.format(
            os.path.basename(path), plist['Entitlements'].get('application-identifier')
        ))

    print('Done. Rewrote {} profiles.'.format(len(profiles)))


if __name__ == '__main__':
    main()
