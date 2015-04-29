#!/usr/bin/env python2.7

"""
functions related to plotting and calculating points on bitcoin's elliptic curve
polynomial (secp256k1): y^2 = x^3 + 7

this file is standalone - it is just for understanding concepts, not used for
calculating real public or private keys.
"""

from distutils.version import LooseVersion
import sympy, mpmath, numpy, matplotlib
import matplotlib.pyplot as plt

if LooseVersion(mpmath.__version__) < LooseVersion("0.19"):
	raise ImportError(
		"mpmath 0.19 or later is required. install it with `sudo python -m"
		" easy_install mpmath`"
	)

if LooseVersion(sympy.__version__) < LooseVersion("0.7.6"):
	raise ImportError(
		"sympy 0.7.6 or later is required. install it with `sudo python -m"
		" easy_install sympy`"
	)

if LooseVersion(matplotlib.__version__) < LooseVersion("1.1.1"):
	raise ImportError(
		"matplotlib 1.1.1 or later is required. install it with `sudo apt-get"
		" install matplotlib`"
	)

################################################################################
# begin curve and line equations
################################################################################

def find_ints_on_curve(max_x):
	"""hint - there aren't any below x = 10,000,000"""
	x = 0
	while x <= max_x:
		mid_x = x**3 + 7
		y = mid_x**0.5
		y_int = int(y)
		recalc_mid_x = y_int**2
		if recalc_mid_x == mid_x:
		#if y_int == y: # don't use this - it fails due to rounding errors
			print "x = ", x, "y = ", y
		x += 1

def y_ec(xp, yp_pos):
	"""
	return either the value of y at point x = xp, or the equation for y in terms
	of xp. xp defines the scalar value of y but does not specify whether the
	result is in the top or the bottom half of the curve. the yp_pos input gives
	this:
	yp_pos == True means yp is a positive value: y = +(x^3 + 7)^0.5
	yp_pos == False means yp is a negative value: y = -(x^3 + 7)^0.5
	"""
	y = sympy.sqrt(xp**3 + 7)
	return y if yp_pos else -y

def y_line(x, p, m):
	"""
	either calculate and return the value of y at point x on the line passing
	through (xp, yp) with slope m, or return the symbolic expression for y as a
	function of x along the line:
	y = mx + c
	ie yp = m(xp) + c
	ie c = yp - m(xp)
	ie y = mx + yp - m(xp)
	ie y = m(x - xp) + yp
	"""
	(xp, yp) = p
	return m * (x - xp) + yp

def slope(p, q):
	"""
	either calculate and return the value of the slope of the line which passes
	through (xp, yp) and (xq, yq) or return the symbolic expression for this
	slope
	"""
	if p == q:
		# when both points are on top of each other then we need to find the
		# tangent slope at (xp, yp)
		return tan_slope(p)
	else:
		# p and q are two different points
		return non_tan_slope(p, q)

def tan_slope(p):
	"""
	calculate the slope of the tangent to curve y^2 = x^3 + 7 at xp.

	the curve can be written as y = (x^3 + 7)^0.5 (positive and negative) and
	the slope of the tangent is the derivative:
	m = dy/dx = (+-)(0.5(x^3 + 7)^-0.5)(3x^2)
	m = (+-)3x^2 / (2(x^3 + 7)^0.5)
	m = 3x^2 / 2y
	"""
	(xp, yp) = p
	return (3 * xp**2) / (2 * yp)

def non_tan_slope(p, q):
	"""
	either calculate and return the value of the slope of the line which passes
	through (xp, yp) and (xq, yq) where p != q, or return the symbolic
	expression for this slope. the slope is the y-step over the x-step, ie
	m = (yp - yq) / (xp - xq)
	"""
	(xp, yp) = p
	(xq, yq) = q
	return (yp - yq) / (xp - xq)

def intersection(p, q):
	"""
	either calculate and return the value of the intersection coordinates of the
	line through (xp, yp) and (xq, yq) with the curve, or the symbolic
	expressions for the coordinates at this point.

	ie the intersection of line y = mx + c with curve y^2 = x^3 + 7.

	in y_line() we found y = mx + c has c = yp - m(xp) and the line and curve
	will have the same y coordinate and x coordinate at their intersections, so:

	(mx + c)^2 = x^3 + 7
	ie (mx)^2 + 2mxc + c^2 = x^3 + 7
	ie x^3 - (m^2)x^2 - 2mcx + 7 - c^2 = 0

	and we already know 2 roots of this equation (ie values of x which satisfy
	the equation) - we know that the curve and line intersect at (xp, yp) and
	at (xq, yq) :)

	the equation is order 3 so it must have 3 roots, and can be written like so:

	(x - r1)(x - r2)(x - r3) = 0
	ie (x^2 - xr2 - xr1 + r1r2)(x - r3) = 0
	ie (x^2 + (-r1 - r2)x + r1r2)(x - r3) = 0
	ie x^3 + (-r1 - r2)x^2 + xr1r2 - (r3)x^2 + (-r3)(-r1 - r2)x - r1r2r3 = 0
	ie x^3 + (-r1 - r2 - r3)x^2 + (r1r2 + r1r3 + r2r3)x - r1r2r3 = 0

	comparing terms:
	-m^2 = -r1 - r2 - r3
	and -2mc = r1r2 + r1r3 + r2r3
	and 7 - c^2 = -r1r2r3

	and since r1 = xp and r2 = xq we can just pick one of these equations to
	solve for r3. the first looks simplest:

	m^2 = r1 + r2 + r3
	ie r3 = m^2 - r1 - r2
	ie r3 = m^2 - xp - xq

	this r3 is the x coordinate of the intersection of the line with the curve.
	"""
	m = slope(p, q)
	(xp, yp) = p
	(xq, yq) = q
	r3 = m**2 - xp - xq
	return (r3, y_line(r3, p, m))
	#return (r3, y_line(r3, q, m)) # would also return the exact same thing

def add_points(p, q):
	"""
	add points (xp, yp) and (xq, yq) by finding the line through them and its
	intersection with the elliptic curve (xr, yr), then mirroring point r about
	the x-axis
	"""
	r = intersection(p, q)
	(xr, yr) = r
	return (xr, -yr)

################################################################################
# end curve and line equations
################################################################################

################################################################################
# begin functions for plotting graphs
################################################################################

# increase this to plot a finer-grained curve - good for zooming in.
# note that this does not affect lines (which only require 2 points).
curve_steps = 10000

def init_plot_ec(x_max = 4, color = "b"):
	"""
	initialize the elliptic curve plot - create the figure and plot the curve
	but do not put any multiplication lines on it yet and don't show it yet.

	we need to determine the minimum x value on the curve. y = sqrt(x^3 + 7) has
	imaginary values when (x^3 + 7) < 0, eg x = -2 -> y = sqrt(-8 + 7) = i,
	which is not a real number. so x^3 = -7, ie x = -cuberoot(7) is the minimum
	real value of x.
	"""
	global plt, x_text_offset, y_text_offset
	x_min = -(7**(1 / 3.0))

	x_text_offset = (x_max - x_min) / 20
	y_max = y_ec(x_max, yp_pos = True)
	y_min = y_ec(x_max, yp_pos = False)
	y_text_offset = (y_max - y_min) / 20

	x = sympy.symbols("x")
	y = sympy.lambdify(x, y_ec(x, yp_pos = True), 'numpy')
	plt.figure() # init
	plt.grid(True)
	x_array = numpy.linspace(x_min, x_max, curve_steps)
	# the top half of the elliptic curve
	plt.plot(x_array, y(x_array), color)
	plt.plot(x_array, -y(x_array), color)
	plt.ylabel("y")
	plt.xlabel("x")
	plt.title("secp256k1: y^2 = x^3 + 7")

def plot_add(p, q, p_name, q_name, p_plus_q_name, color = "r"):
	"""
	add-up two points on the curve (p & q). this involves plotting a line
	through both points and finding the third intersection with the curve (r),
	then mirroring that point about the x axis. note that it is possible for the
	intersection to fall between p and q.
	"""
	global plt, x_text_offset, y_text_offset
	(xp, yp) = p
	(xq, yq) = q
	# first, plot the line between the two points upto the intersection with the
	# curve...

	# get the point of intersection (r)
	(xr, yr) = intersection(p, q)
	# get the range of values the x axis covers
	x_min = min(xp, xq, xr)
	x_max = max(xp, xq, xr)

	# a line only needs two points
	x_array = numpy.linspace(x_min, x_max, 2)

	m = slope(p, q)
	y_array = y_line(x_array, p, m)
	plt.plot(x_array, y_array, color)

	# plot a point at p
	plt.plot(xp, yp, "%so" % color)

	# name the point at p
	plt.text(xp - x_text_offset, yp + y_text_offset, p_name)

	if p is not q:
		# plot a point at q
		plt.plot(xq, yq, "%so" % color)

		# name the point at q
		plt.text(xq - x_text_offset, yq + y_text_offset, q_name)

	# second, plot the vertical line to the other half of the curve...
	y_array = numpy.linspace(yr, -yr, 2)
	x_array = numpy.linspace(xr, xr, 2)
	plt.plot(x_array, y_array, "%s" % color)
	plt.plot(xr, -yr, "%so" % color)
	plt.text(xr - x_text_offset, -yr + y_text_offset, p_plus_q_name)

def finalize_plot_ec(save, img_filename = None):
	"""
	either display the graph as a new window or save the graph as an image and
	write a link to the image in the results file
	"""
	global plt
	# don't block, so that we can keep the graph open while proceeding with the
	# rest of the tests
	if save:
		plt.savefig("results/%s.png" % img_filename, bbox_inches = "tight")
		with open(md_file, "ab") as f:
			f.write("![%s](%s.png)\n" % (img_filename, img_filename))

	else:
		plt.show(block = False)

################################################################################
# end functions for plotting graphs
################################################################################

if __name__ == "__main__":

	hr = """
-------------
"""

	import sys
	markdown = True if "-m" in sys.argv else False
	if markdown:
		import os, errno, hashlib
		# create the results directory to store the graph and equation images in
		try:
			os.makedirs("results")
		except OSError as exception:
			if exception.errno != errno.EEXIST:
				raise
		md_file = "results/ec_poly.md"
		print """
writing output to %s
""" % md_file
		print hr
		with open(md_file, "w") as f:
			f.write("# output from `./ec_poly.py -m`\n\n")

		# function to generate an image from an equation and write a link to it
		def save_and_link_to_img(eq):
			global plt
			latex_output = sympy.latex(eq)
			img_filename = hashlib.sha1(latex_output).hexdigest()[: 10]

			# create the figure and hide the border. set the height and width to
			# something far smaller than the resulting image - bbox_inches will
			# expand this later
			fig = plt.figure(figsize = (0.1, 0.1), frameon = False)
			ax = fig.add_axes([0, 0, 1, 1])
			ax.axis("off")
			fig = plt.gca()
			fig.axes.get_xaxis().set_visible(False)
			fig.axes.get_yaxis().set_visible(False)
			plt.text(0, 0, r"$%s$" % latex_output, fontsize = 25)
			plt.savefig("results/%s.png" % img_filename, bbox_inches = "tight")
			with open(md_file, "ab") as f:
				# don't use the entire latex string for the alt text as it could
				# be very long
				f.write("![%s](%s.png)\n" % (latex_output[: 20], img_filename))

	else:
		print """
%sto output in markdown format, invoke this script with the "-m" flag, like so:

./ec_poly.py -m

(images are saved into a results/ subdir, which is created if necessary)%s""" \
% (hr, hr)

	# detect the best form of pretty printing available in this terminal
	sympy.init_printing()

	decimal_places = 30

	xp = 1
	yp_pos = True
	output = """
the intersection of the tangent line at x = %s (%s y) with the curve in
non-reduced form:

""" % (xp, "positive" if yp_pos else "negative")
	print output
	if markdown:
		with open(md_file, "ab") as f:
			f.write(output)

	yp = y_ec(xp, yp_pos)
	p = (xp, yp)
	(xr, yr) = intersection(p, p)
	sympy.pprint((xr, yr))
	if markdown:
		save_and_link_to_img((xr, yr))

	print hr
	if markdown:
		with open(md_file, "ab") as f:
			f.write(hr)

	msg = "press enter to continue"
	raw_input(msg)

	xp = 1
	yp_pos = True
	output = """
the intersection of the tangent line at x = %s (%s y) with the curve in reduced
form:

""" % (xp, "positive" if yp_pos else "negative")
	print output
	if markdown:
		with open(md_file, "ab") as f:
			f.write(output)

	# first we need the y-coordinate of the curve at xp
	yp = y_ec(xp, yp_pos)

	# now we have the point on the curve
	p = (xp, yp)
	(xr, yr) = intersection(p, p)
	output = (xr.evalf(decimal_places), yr.evalf(decimal_places))
	print output
	print hr
	if markdown:
		with open(md_file, "ab") as f:
			f.write("`%s`\n" % (output, ))
			f.write(hr)

	raw_input(msg)

	yp_pos = True
	output = """
the equation of the tangent line which passes through x = xp (%s y) on the
curve:

""" % "positive" if yp_pos else "negative"
	print output
	if markdown:
		with open(md_file, "ab") as f:
			f.write(output)

	(x, xp) = sympy.symbols("x xp")

	# first we need the y-coordinate of the curve at xp
	yp = y_ec(xp, yp_pos)

	# now we have the point on the curve
	p = (xp, yp)
	m = slope(p, p)
	print "y = "
	print
	output = y_line(x, p, m)
	sympy.pprint(output)
	print hr
	if markdown:
		with open(md_file, "ab") as f:
			f.write("`y = `")

		save_and_link_to_img(output)

		with open(md_file, "ab") as f:
			f.write(hr)

	raw_input(msg)

	output = """
the equation of the bitcoin elliptic curve:

"""
	print output
	if markdown:
		with open(md_file, "ab") as f:
			f.write(output)

	print "y = "
	print
	output = y_ec(sympy.symbols("x"), yp_pos = True)
	sympy.pprint(output)
	if markdown:
		with open(md_file, "ab") as f:
			f.write("`y = `")

		save_and_link_to_img(output)

	print
	print
	print "and y = "
	print
	output = y_ec(sympy.symbols("x"), yp_pos = False)
	sympy.pprint(output)
	print hr
	if markdown:
		with open(md_file, "ab") as f:
			f.write("\n\nand `y = `")

		save_and_link_to_img(output)

		with open(md_file, "ab") as f:
			f.write(hr)

	raw_input(msg)

	xp = 10
	yp_pos = True
	output = """
plot the bitcoin elliptic curve and visually check that p + p + p + p = 2p + 2p
using xp = %s (%s y):

""" % (xp, "positive" if yp_pos else "negative")

	print output
	if markdown:
		with open(md_file, "ab") as f:
			f.write(output)

	# first calculate the rightmost x coordinate for the curve
	yp = y_ec(xp, yp_pos)
	p = (xp, yp)
	two_p = add_points(p, p)
	three_p = add_points(p, two_p)
	four_p = add_points(p, three_p)
	(x2p, y2p) = two_p
	(x3p, y3p) = three_p
	(x4p, y4p) = four_p
	rightmost_x = max(xp, x2p, x3p, x4p)

	init_plot_ec(rightmost_x + 2)
	plot_add(p, p, "p", "p", "2p", color = "r")
	plot_add(p, two_p, "p", "2p", "3p", color = "c")
	plot_add(p, three_p, "p", "3p", "4p", color = "g")
	plot_add(two_p, two_p, "2p", "2p", "4p", color = "y")
	finalize_plot_ec(True if markdown else False, "graph1")
	print hr
	if markdown:
		with open(md_file, "ab") as f:
			f.write(hr)

	exit()
	raw_input(msg)

	print """
calculate the intersection of the curve with p + p + p + p and check that it is
equal to the intersection of the curve with 2p + 2p

"""

	# use xp, yp_pos from the previous test (easier to visualize)
	# P + P + P + P
	print "p + p + p + p = %s" % (four_p, )

	# 2P + 2P
	two_p_plus_2p = add_points(two_p, two_p)
	print
	print "2p + 2p = %s" % (two_p_plus_2p, )
	print "-------------"
	raw_input(msg)

	print """
calculate the intersection of the curve with p + p + p + p for an arbitrary p of
(xp, yp) and check that it is equal to the intersection of the curve with
2p + 2p

"""

	xp = sympy.symbols("xp")

	# choose a point where y < 0
	yp = y_ec(xp, yp_pos)
	p = (xp, yp)
	two_p = add_points(p, p)
	three_p = add_points(p, two_p)
	four_p = add_points(p, three_p)
	(x4p, y4p) = four_p
	print "x @ p + p + p + p:"
	print
	sympy.pprint(x4p.simplify())
	print
	print "y @ p + p + p + p:"
	print
	sympy.pprint(y4p.simplify())

	two_p_plus_2p = add_points(two_p, two_p)
	(x2p_plus_2p, y2p_plus_2p) = two_p_plus_2p 
	print
	print "x @ 2p + 2p:"
	print
	sympy.pprint(x2p_plus_2p.simplify())
	print
	print "y @ 2p + 2p:"
	print
	sympy.pprint(y2p_plus_2p.simplify())
	print
	print "should be 0 if x @ p + p + p + p = x @ 2p + 2p:"
	print
	sympy.pprint((x4p - x2p_plus_2p).simplify())
	print
	print "should be 0 if y @ p + p + p + p = y @ 2p + 2p:"
	print
	sympy.pprint((y4p - y2p_plus_2p).simplify())
	print "-------------"
	raw_input(msg)

	# don't set k too high or it will produce huge numbers that cannot be
	# computed and plotted. k = 7 seems to be about the limit for this simple
	# script
	k = 7
	xp0 = 10
	yp_pos = True
	print """
plot the bitcoin elliptic curve and add point xp = %s (%s y) to itself %s times

""" % (xp0, "positive" if yp_pos else "negative", k)

	# first calculate the rightmost x coordinate for the curve
	yp0 = y_ec(xp0, yp_pos)
	p = []
	p.append((xp0, yp0))
	rightmost_x = xp0 # init
	for i in xrange(1, k + 1):
		p.append(add_points(p[0], p[i - 1]))
		(xpi, ypi) = p[i]
		if xpi > rightmost_x:
			rightmost_x = xpi

	init_plot_ec(rightmost_x + 2)
	for i in xrange(1, k + 1):
		# alternate between red and green - makes it easier to distinguish
		# addition lines
		color = "g" if (i % 2) else "r"
		plot_add(p[0], p[i - 1], "p", "" % (), "%sp" % (i + 1), color = color)

	finalize_plot_ec()
	print "-------------"
	raw_input(msg)

	print """
visually demonstrate the functionality of a master public/private key

"""
	# TODO

	print "-------------"
	raw_input("press enter to exit")
