#!/usr/bin/env python2.7
# parse the readme file as python option arguments

from optparse import OptionParser

# init the vars
synopsis = "Usage: "
heading = ""
old_heading = ""
option_indent = "       " # tweak this according to the readme file - it needs to be exact
help_string = ""

readme_file = open("README.md", "r") # get the file object
for line in readme_file:
	if line[0].isupper(): # this is a heading line
		old_heading = heading
		heading = line.strip()
		if old_heading != heading: # the heading just changed
			if old_heading == "SYNOPSIS": # just finished parsing the synopsis
				synopsis = synopsis.strip() # clear trailing space char
			if old_heading == "DESCRIPTION": # just finished parsing the description
				description = description.strip() # clear trailing space char
				arg_parser = OptionParser(usage = synopsis, description = description)
			if old_heading == "OPTIONS": # just finished parsing the options
				break # stop reading lines from the file
	line = line.strip()
	if not line:
		continue # ignore blank lines
	line = line + " "
	if heading == "SYNOPSIS":
		synopsis = synopsis + line
	if heading == "DESCRIPTION":
		description = description + line
	if heading == "OPTIONS":
		if line[ : len(option_indent + "-")] == (option_indent + "-"): # this is the start of a new option
			# first, add the previous option data
			
			if short_arg and long_arg:
				arg_parser.add_option("-a", "--addresses", action = "store", dest = "ADDRESSES", help = "Specify the ADDRESSES for which data is to be extracted from the blockchain files. ADDRESSES is a comma-seperated list and all ADDRESSES must be from the same cryptocurrency.")
			arg_parser.add_option(**arg_list)
			# now clear the previous option data and gather new data
			arg_list = {}
			line = line.strip()
			if "," in line:
				(short_arg_string, long_arg_string) = line.split(",")
				if " " in short_arg_string:
					(short_arg, dest_short) = short_arg_string.split(" ")
					arg_list[0] = short_arg.strip()
					arg_list["dest"] = dest_short.strip()
				else:
					arg_list[0] = short_arg_string.strip()
				if "=" in long_arg_string:
					(long_arg, dest_long) = long_arg_string.split("=")
					arg_list[1] = long_arg.strip()
					arg_list["dest"] = dest_long.strip()
				else:
					arg_list[1] = long_arg_string
			else:
				if " " in short_arg_string:
					(short_arg, dest_short) = short_arg_string.split(" ")
					arg_list[0] = short_arg.strip()
					arg_list["dest"] = dest_short.strip()
				else:
					arg_list[0] = short_arg_string.strip()
				if "=" in long_arg_string:
					(long_arg, dest_long) = long_arg_string.split("=")
					arg_list[1] = long_arg.strip()
					arg_list["dest"] = dest_long.strip()
				else:
					arg_list[1] = long_arg_string
		else:
			line = line.strip()
			arg_list["help"] = arg_list["help"] + line

readme_file.close()
