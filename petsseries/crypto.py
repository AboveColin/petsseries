
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import padding

def decrypt_image(encrypted_data: bytes, key_string: str) -> bytes:
    """
    Decrypts an image from the Tuya/Philips Pet Series S3 bucket.
    
    Args:
        encrypted_data: The raw bytes downloaded from the S3 URL.
        key_string: The thumbnail_key from the event metadata.
        
    Returns:
        Decrypted image bytes.
    """
    if not encrypted_data or not key_string:
        return b""

    # key_string is utf-8 encoded to get bytes
    key = key_string.encode('utf-8')
    
    # Parse Header based on DecryptImageRequest.java
    # 0-3: Version (int, big endian)
    # version = int.from_bytes(encrypted_data[0:4], byteorder='big')
    
    # 4-20: IV (16 bytes)
    iv = encrypted_data[4:20]
    
    # 20-24: Skip 4 bytes
    
    # Determine offset and level
    offset = 24
    header_version = int.from_bytes(encrypted_data[0:4], byteorder='big')
    
    level = 3 # Default AES
    
    if header_version == 2:
        level = encrypted_data[offset]
        offset += 1
    else:
        offset += 1 # inputStream.skip(1L)
        level = 3
        
    # Skip 39 bytes (header padding/metadata)
    offset += 39
    
    # Remaining is ciphertext
    ciphertext = encrypted_data[offset:]
    
    if level == 3:
        # AES CBC
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
        decryptor = cipher.decryptor()
        
        # update() + finalize()
        padded_plaintext = decryptor.update(ciphertext) + decryptor.finalize()
        
        # Unpad (PKCS7/PKCS5)
        # AES block size is 128 bits (16 bytes)
        unpadder = padding.PKCS7(128).unpadder()
        try:
            plaintext = unpadder.update(padded_plaintext) + unpadder.finalize()
            return plaintext
        except Exception as e:
            # Fallback or error logging
            print(f"Error unpadding or decrypting: {e}")
            return b""
            
    # TODO: Implement other levels if encountered (ChaCha20, GCM)
    
    return b""
