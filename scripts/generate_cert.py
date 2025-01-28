"""Generate self-signed certificates for development HTTPS."""

from OpenSSL import crypto
import os

def generate_self_signed_cert(cert_dir="certs"):
    """Generate self-signed certificate and private key."""
    
    # Create certificates directory if it doesn't exist
    if not os.path.exists(cert_dir):
        os.makedirs(cert_dir)
    
    # Generate key
    key = crypto.PKey()
    key.generate_key(crypto.TYPE_RSA, 2048)
    
    # Generate certificate
    cert = crypto.X509()
    cert.get_subject().C = "US"
    cert.get_subject().ST = "CA"
    cert.get_subject().L = "San Francisco"
    cert.get_subject().O = "Shronas"
    cert.get_subject().OU = "Beacon"
    cert.get_subject().CN = "127.0.0.1"
    
    # Add Subject Alternative Name
    cert.add_extensions([
        crypto.X509Extension(b"subjectAltName", False, b"DNS:localhost, IP:127.0.0.1")
    ])
    
    cert.set_serial_number(1000)
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(365*24*60*60)  # Valid for one year
    cert.set_issuer(cert.get_subject())
    cert.set_pubkey(key)
    cert.sign(key, 'sha256')
    
    # Write certificate and private key to files
    with open(os.path.join(cert_dir, "cert.pem"), "wb") as f:
        f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert))
    
    with open(os.path.join(cert_dir, "key.pem"), "wb") as f:
        f.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, key))

if __name__ == "__main__":
    generate_self_signed_cert() 