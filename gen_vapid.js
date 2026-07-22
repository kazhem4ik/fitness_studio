const crypto = require('crypto');

// Generate P-256 key pair
const { privateKey, publicKey } = crypto.generateKeyPairSync('ec', {
    namedCurve: 'P-256'
});

// Public key: uncompressed point (04 || x || y), base64url encoded
const pubRaw = publicKey.export({ type: 'spki', format: 'der' });
// Last 65 bytes of SPKI DER are the uncompressed public key
const pubBytes = pubRaw.slice(-65);
const pubB64 = pubBytes.toString('base64').replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '');

// Private key: raw 32-byte scalar, base64url encoded
const privDer = privateKey.export({ type: 'pkcs8', format: 'der' });
// Private key scalar is at offset 36, 32 bytes
const privBytes = privDer.slice(36, 68);
const privB64 = privBytes.toString('base64').replace(/\+/g, '-').replace(/\//g, '_').replace(/=/g, '');

console.log('PUBLIC:', pubB64);
console.log('PRIVATE:', privB64);
console.log('pub length:', pubBytes.length);
console.log('priv length:', privBytes.length);
console.log('first pub byte:', pubBytes[0].toString(16), '(should be 04)');
