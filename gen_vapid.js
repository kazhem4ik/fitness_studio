const { createECDH } = require('crypto');

// prime256v1 = P-256
const ecdh = createECDH('prime256v1');
ecdh.generateKeys();

// getPublicKey() returns 65 bytes: 04 || x || y (uncompressed point)
const pubBytes = ecdh.getPublicKey(); // Buffer
const pubB64 = pubBytes.toString('base64url');

// getPrivateKey() returns 32 bytes raw scalar
const privBytes = ecdh.getPrivateKey(); // Buffer
const privB64 = privBytes.toString('base64url');

console.log('PUBLIC:', pubB64);
console.log('PRIVATE:', privB64);
console.log('pub length:', pubBytes.length, '(should be 65)');
console.log('priv length:', privBytes.length, '(should be 32)');
console.log('first pub byte:', pubBytes[0].toString(16), '(should be 04)');
