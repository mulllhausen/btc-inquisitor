"""python wrapper for ecdsa ssl"""

# modified from
# https://github.com/jgarzik/python-bitcoinlib/blob/master/bitcoin/key.py

import ctypes, ctypes.util
import lang_grunt

# constants
POINT_CONVERSION_COMPRESSED = 2
POINT_CONVERSION_UNCOMPRESSED = 4
NID_secp256k1 = 714 # from openssl/obj_mac.h

def check_result(val, func, args):
	# thanks to sam devlin for the ctypes magic 64-bit fix
	if val == 0:
		raise ValueError
	else:
		return ctypes.c_void_p(val)

def init():
	global ssl, k
	ssl = ctypes.cdll.LoadLibrary(ctypes.util.find_library('ssl') or 'libeay32')
	ssl.EC_KEY_new_by_curve_name.restype = ctypes.c_void_p
	ssl.EC_KEY_new_by_curve_name.errcheck = check_result
	k = ssl.EC_KEY_new_by_curve_name(NID_secp256k1)
	# use uncompressed keys by default
	ssl.EC_KEY_set_conv_form(k, POINT_CONVERSION_UNCOMPRESSED)

def reset():
	global ssl, k
	if ssl:
		ssl.EC_KEY_free(k)
	k = None

def generate(secret = None):
	"""
	generate a new key object. if the secret argument is specified then generate
	a deterministic key, otherwise seed the key with a random number to retrieve
	a random key.
	"""
	if secret is None:
		return ssl.EC_KEY_generate_key(k)
	else:
		priv_key = ssl.BN_bin2bn(secret, 32, ssl.BN_new())
		group = ssl.EC_KEY_get0_group(k)
		pub_key = ssl.EC_POINT_new(group)
		ctx = ssl.BN_CTX_new()
		if not ssl.EC_POINT_mul(group, pub_key, priv_key, None, None, ctx):
			lang_grunt.die(
				"could not derive public key from the supplied secret"
				# (don't print the secret, for security)
			)
		ssl.EC_KEY_set_private_key(k, priv_key)
		ssl.EC_KEY_set_public_key(k, pub_key)
		ssl.EC_POINT_free(pub_key)
		ssl.BN_CTX_free(ctx)
		return k

def set_privkey(key):
	mb = ctypes.create_string_buffer(key)
	ssl.d2i_ECPrivateKey(
		ctypes.byref(k), ctypes.byref(ctypes.pointer(mb)), len(key)
	)

def set_pubkey(key):
	mb = ctypes.create_string_buffer(key)
	ssl.o2i_ECPublicKey(
		ctypes.byref(k),
		ctypes.byref(ctypes.pointer(mb)),
		len(key)
	)

def get_privkey():
	size = ssl.i2d_ECPrivateKey(k, 0)
	mb_pri = ctypes.create_string_buffer(size)
	ssl.i2d_ECPrivateKey(k, ctypes.byref(ctypes.pointer(mb_pri)))
	return mb_pri.raw

def get_pubkey():
	size = ssl.i2o_ECPublicKey(k, 0)
	mb = ctypes.create_string_buffer(size)
	ssl.i2o_ECPublicKey(k, ctypes.byref(ctypes.pointer(mb)))
	return mb.raw

def sign(plaintext):
	sig_size0 = ctypes.c_uint32()
	sig_size0.value = ssl.ECDSA_size(k)
	mb_sig = ctypes.create_string_buffer(sig_size0.value)
	result = ssl.ECDSA_sign(
		0, plaintext, len(plaintext), mb_sig, ctypes.byref(sig_size0), k
	)
	assert 1 == result
	return mb_sig.raw[:sig_size0.value]

def verify(plaintext, sig):
	return 1 == ssl.ECDSA_verify(0, plaintext, len(plaintext), sig, len(sig), k)

def set_compressed(compressed):
	if compressed:
		form = POINT_CONVERSION_COMPRESSED
	else:
		form = POINT_CONVERSION_UNCOMPRESSED
	ssl.EC_KEY_set_conv_form(k, form)
