#!/usr/bin/env python2.7

# convert database in the format ~/.btc-inquisitor/tx_metadata/00/01/02/03/04/
# 05/06/07/08/09/10/11/12/13/14/15/16/17/18/19/20/21/22/23/24/25/26/27/28/29/
# 30/31.txt
# to ~/.btc-inquisitor/tx_metadata/01/02/03.txt where the remainder of the hash
# is inside file 03.txt

import os
import glob
import shutil

copy_dir = os.path.expanduser("~/.btc-inquisitor/tx_metadata")
#copy_dir = os.path.expanduser("/tmp/tx_metadata") # debug use only
paste_root_dir = os.path.expanduser("~/.btc-inquisitor/tx_metadata")
#paste_root_dir = os.path.expanduser("/tmp/tx_meta_new") # debug use only
l = len(".txt")

for num1 in range(256):
	print "remodel dir: %s/%02x" % (copy_dir, num1)

	for num2 in range(256):
		print "remodel dir: %s/%02x/%02x" % (copy_dir, num1, num2)

		for num3 in range(256):

			paste_file = "%s/%02x/%02x/%02x.txt" % \
			(paste_root_dir, num1, num2, num3)
			paste_dir = os.path.dirname(paste_file)

			buff = [] # init the buffer for data that will be written to file

			for abs_file in glob.iglob(
				"%s/%02x/%02x/%02x/*/*/*/*/*/*/*/*/*/*/*/*/*/*/*/*/*/*/*/*/*/*/"
				"*/*/*/*/*/*/*.txt" % (copy_dir, num1, num2, num3)
			):
				part_hash = abs_file[len(copy_dir) + 10: -l].replace("/", "")

				with open(abs_file, "r") as f:
					# get each line of the file into a list element
					file_contents = f.read().splitlines()

				# add to buffer
				for line in file_contents:
					buff.append("%s,%s" % (part_hash, line))

			if buff:
				print "write to file %s" % paste_file

				# create directory if necessary
				if not os.path.exists(paste_dir):
					os.makedirs(paste_dir)

				# write buffer to file
				with open(paste_file, "w") as write_file:
					write_file.write("\n".join(buff))

				del_dir = "%s/%02x/%02x/%02x" % (copy_dir, num1, num2, num3)
				if os.path.exists(del_dir):
					shutil.rmtree(del_dir)

		#break # debug use only

	#break # debug use only
