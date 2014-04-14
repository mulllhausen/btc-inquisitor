"""python wrapper for ecdsa ssl"""

# modified from:
# - https://github.com/jgarzik/python-bitcoinlib/blob/master/bitcoin/key.py
# - https://github.com/samrushing/caesure/blob/master/ecdsa_ssl.py
# - https://github.com/samrushing/caesure/blob/master/ecdsa_ssl.py

import ctypes, ctypes.util

ssl = ctypes.cdll.LoadLibrary(ctypes.util.find_library('ssl') or 'libeay32')
NID_secp256k1 = 714 # this specifies the specific ecdsa curve in use. from openssl/obj_mac.h

def check_result(val, func, args):
	# thanks to sam devlin for the ctypes magic 64-bit fix
	if val == 0:
		raise ValueError
	else:
		return ctypes.c_void_p(val)

ssl.EC_KEY_new_by_curve_name.restype = ctypes.c_void_p
ssl.EC_KEY_new_by_curve_name.errcheck = check_result

class key:

	def __init__(self):
		self.POINT_CONVERSION_COMPRESSED = 2
		self.POINT_CONVERSION_UNCOMPRESSED = 4
		self.k = ssl.EC_KEY_new_by_curve_name(NID_secp256k1)

	def __del__(self):
		if ssl:
			ssl.EC_KEY_free(self.k)
		self.k = None

	def generate(self, secret=None):
		if secret:
			self.prikey = secret
			priv_key = ssl.BN_bin2bn(secret, 32, ssl.BN_new())
			group = ssl.EC_KEY_get0_group(self.k)
			pub_key = ssl.EC_POINT_new(group)
			ctx = ssl.BN_CTX_new()
			if not ssl.EC_POINT_mul(group, pub_key, priv_key, None, None, ctx):
				raise ValueError("could not derive public key from the supplied secret")
			ssl.EC_POINT_mul(group, pub_key, priv_key, None, None, ctx)
			ssl.EC_KEY_set_private_key(self.k, priv_key)
			ssl.EC_KEY_set_public_key(self.k, pub_key)
			ssl.EC_POINT_free(pub_key)
			ssl.BN_CTX_free(ctx)
			return self.k
		else:
			return ssl.EC_KEY_generate_key(self.k)

	def set_privkey(self, key):
		self.mb = ctypes.create_string_buffer(key)
		ssl.d2i_ECPrivateKey(ctypes.byref(self.k), ctypes.byref(ctypes.pointer(self.mb)), len(key))

	def set_pubkey(self, key):
		self.mb = ctypes.create_string_buffer(key)
		ssl.o2i_ECPublicKey(ctypes.byref(self.k), ctypes.byref(ctypes.pointer(self.mb)), len(key))

	def get_privkey(self):
		size = ssl.i2d_ECPrivateKey(self.k, 0)
		mb_pri = ctypes.create_string_buffer(size)
		ssl.i2d_ECPrivateKey(self.k, ctypes.byref(ctypes.pointer(mb_pri)))
		return mb_pri.raw

	def get_pubkey(self):
		size = ssl.i2o_ECPublicKey(self.k, 0)
		mb = ctypes.create_string_buffer(size)
		ssl.i2o_ECPublicKey(self.k, ctypes.byref(ctypes.pointer(mb)))
		return mb.raw

	def sign(self, hash):
		sig_size0 = ctypes.c_uint32()
		sig_size0.value = ssl.ECDSA_size(self.k)
		mb_sig = ctypes.create_string_buffer(sig_size0.value)
		result = ssl.ECDSA_sign(0, hash, len(hash), mb_sig, ctypes.byref(sig_size0), self.k)
		assert 1 == result
		return mb_sig.raw[:sig_size0.value]

	def verify(self, hash, sig):
		return 1 == ssl.ECDSA_verify(0, hash, len(hash), sig, len(sig), self.k)

	def set_compressed(self, compressed):
		if compressed:
			form = self.POINT_CONVERSION_COMPRESSED
		else:
			form = self.POINT_CONVERSION_UNCOMPRESSED
		ssl.EC_KEY_set_conv_form(self.k, form)
