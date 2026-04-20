from PIL import Image
import numpy as np
import matplotlib.pyplot as plt
from Crypto.Cipher import AES, DES
from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import pad, unpad

# --- load image ---
image = Image.open("gg.jpg").convert("L")
image_array = np.array(image)
data = image_array.tobytes()

# =========================
# AES KEY
# =========================
key_aes = get_random_bytes(16)

# =========================
# ECB MODE (AES)
# =========================
cipher_ecb = AES.new(key_aes, AES.MODE_ECB)
ciphertext_ecb = cipher_ecb.encrypt(pad(data, AES.block_size))

ecb_array = np.frombuffer(ciphertext_ecb[:len(data)], dtype=np.uint8)
ecb_array = ecb_array.reshape(image_array.shape)

# =========================
# CBC MODE (AES)
# =========================
iv_aes = get_random_bytes(16)
cipher_cbc = AES.new(key_aes, AES.MODE_CBC, iv_aes)
ciphertext_cbc = cipher_cbc.encrypt(pad(data, AES.block_size))

cbc_array = np.frombuffer(ciphertext_cbc[:len(data)], dtype=np.uint8)
cbc_array = cbc_array.reshape(image_array.shape)

# =========================
# DECRYPT CBC (verification)
# =========================
cipher_cbc_dec = AES.new(key_aes, AES.MODE_CBC, iv_aes)
decrypted_padded = cipher_cbc_dec.decrypt(ciphertext_cbc)
decrypted_data = unpad(decrypted_padded, AES.block_size)

decrypted_array = np.frombuffer(decrypted_data, dtype=np.uint8)
decrypted_array = decrypted_array.reshape(image_array.shape)

# =========================
# DES (CBC MODE)
# =========================
key_des = get_random_bytes(8)   # DES needs 8 bytes
iv_des = get_random_bytes(8)

cipher_des = DES.new(key_des, DES.MODE_CBC, iv_des)
ciphertext_des = cipher_des.encrypt(pad(data, DES.block_size))

des_array = np.frombuffer(ciphertext_des[:len(data)], dtype=np.uint8)
des_array = des_array.reshape(image_array.shape)

# =========================
# PLOT ALL
# =========================
plt.figure(figsize=(20,5))

plt.subplot(1, 4, 1)
plt.title("Original")
plt.imshow(image_array, cmap="gray")
plt.axis("off")

plt.subplot(1, 4, 2)
plt.title("AES ECB")
plt.imshow(ecb_array, cmap="gray")
plt.axis("off")

plt.subplot(1, 4, 3)
plt.title("AES CBC")
plt.imshow(cbc_array, cmap="gray")
plt.axis("off")

plt.subplot(1, 4, 4)
plt.title("DES CBC")
plt.imshow(des_array, cmap="gray")
plt.axis("off")

plt.suptitle("Image Encryption Comparison", fontsize=14)
plt.tight_layout()
plt.show()