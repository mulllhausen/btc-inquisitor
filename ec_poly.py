#!/usr/bin/env python2.7

"""
functions related to plotting and calculating points on bitcoin's ecdsa
polynomial (secp256k1): y^2 = x^3 + 7

this file is standalone - it is just for understanding concepts, not used for
calculating real public or private keys.
"""
import sympy
# detect the best form of pretty printing available
sympy.init_printing()

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

def y_line(x, xp, yp, m):
	"""
	return either the value of y at point x = xr, or the line equation for y in
	terms of x:
	y = mx + c
	ie yp = m(xp) + c
	ie c = yp - m(xp)
	ie y = mx + yp - m(xp)
	ie y = m(x - xp) + yp
	"""
	return m * (x - xp) + yp

def slope(xp, xq, yp_pos, yq_pos):
	"""return the equation of the slope which passes through points xp and xq"""
	if xp == xq:
		# when both points are on top of each other then we need to find the
		# tangent slope at xp
		return tan_slope(xp, yp_pos)
	else:
		return non_tan_slope(xp, xq, yp_pos, yq_pos)

def tan_slope(xp, yp_pos):
	"""
	calculate the slope of the tangent to curve y^2 = x^3 + 7 at xp.
	the curve can be written as y = (x^3 + 7)^0.5 (positive and negative) and
	the slope of the tangent is the derivative:
	m = dy/dx = (0.5(x^3 + 7)^-0.5)(3x^2)
	m = 3x^2 / (2(x^3 + 7)^0.5)
	m = 3x^2 / 2y
	"""
	return (3 * xp**2) / (2 * y_ec(xp, yp_pos))

def non_tan_slope(xp, xq, yp_pos, yq_pos):
	"""
	calculate the slope of the line that passes through p and q (two different
	points - hence they are not a tangent) on curve y^2 = x^3 + 7. this is just
	the y-step over the x-step - ie m = (yp - yq) / (xp - xq)
	"""
	return (y_ec(xp, yp_pos) - y_ec(xq, yq_pos))/(xp - xq)

def intersection(xp, xq, yp_pos, yq_pos):
	"""
	calculate the intersection coordinates of the line through x = xp and x = xq
	with the curve. ie the intersection of line y = mx + c with curve
	y^2 = x^3 + 7.

	in y_line() we found y = mx + c has c = yp - m(xp) and the line and curve
	will have the same y coordinate and x coordinate at their intersection, so:

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

	or in the case where xp = xq (ie the tangent to the curve), r3 = m^2 - 2xp

	this r3 is the x coordinate of the intersection of the line with the curve.
	"""
	yp = y_ec(xp, yp_pos)
	m = slope(xp, xq, yp_pos, yq_pos)
	r3 = m**2 - xp - xq
	return (r3, y_line(r3, xp, yp, m))

################################################################################
# end curve and line equations
################################################################################

################################################################################
# begin functions for plotting graphs
################################################################################
import numpy
import matplotlib.pyplot as plt

# increase this to plot a finer-grained curve - good for zooming in.
# note that this does not affect lines (which only require 2 points).
curve_steps = 10000

def init_plot_ec(x_max = 4):
	"""
	initialize the eliptic curve plot - create the figure and plot the curve but
	do not put any multiplication lines on it yet and don't show it yet.

	we need to determine the minimum x value on the curve. y = sqrt(x^3 + 7) has
	imaginary values when (x^3 + 7) < 0, eg x = -2 -> y = sqrt(-8 + 7) = i,
	which is not a real number. so x^3 = -7, ie x = -cuberoot(7) is the minimum
	real value of x.
	"""
	global plt
	x_min = -(7**(1 / 3.0))
	x_array = numpy.linspace(x_min, x_max, curve_steps)
	x = sympy.symbols("x")
	y = sympy.lambdify(x, y_ec(x, yp_pos = True), 'numpy')
	plt.figure() # init
	plt.grid(True)
	# plot the eliptic curve in blue
	color = "b"
	plt.plot(x_array, y(x_array), color)
	plt.plot(x_array, -y(x_array), color)
	plt.ylabel("y")
	plt.xlabel("x")
	plt.title("secp256k1: y^2 = x^3 + 7")

def plot_add(
	xp, xq, p_name, q_name, p_plus_q_name, yp_pos, yq_pos, color = "r"
):
	"""
	add-up two points on the curve (p & q). this involves plotting a line
	through both points and finding the third intersection with the curve (r),
	then mirroring that point about the x axis. note that it is possible for the
	intersection to fall between p and q.
	"""
	global plt
	# first, plot the line between the two points upto the intersection with the
	# curve...

	# get the point of intersection (r)
	(xr, yr) = intersection(xp, xq, yp_pos, yq_pos)

	# get the y-coordinate of p
	yp = y_ec(xp, yp_pos)

	# get the range of values for the x axis covers
	x_min = min(xp, xq, xr)
	x_max = max(xp, xq, xr)

	x_array = numpy.linspace(x_min, x_max, 2)
	m = slope(xp, xq, yp_pos, yq_pos)
	y_array = y_line(x_array, xp, yp, m)
	plt.plot(x_array, y_array, color)
	plt.plot(xp, yp, "%so" % color)
	plt.text(xp - 0.1, yp + 0.5, p_name)
	if xp is not xq:
		yq = y_ec(xq, yq_pos)
		plt.plot(xq, yq, "%so" % color)
		plt.text(xq - 0.1, yq + 0.5, q_name)

	# the vertical line to the other half of the curve
	y_array = numpy.linspace(yr, -yr, 2)
	x_array = numpy.linspace(xr, xr, 2)
	plt.plot(x_array, y_array, "%s" % color)
	plt.plot(xr, -yr, "%so" % color)
	plt.text(xr - 0.1, 0.5 - yr, p_plus_q_name)

def finalize_plot_ec():
	global plt
	# don't block, so that we can keep the graph open while proceeding with the
	# rest of the tests
	plt.show(block = False)

################################################################################
# end functions for plotting graphs
################################################################################

if __name__ == "__main__":
	decimal_places = 50

	xp = 1
	yp_pos = True
	print """
the intersection of the tangent line at x = %s (%s y) with the curve in
non-reduced form

""" % (xp, "positive" if yp_pos else "negative")

	xp = 1
	xq = xp
	yq_pos = yp_pos
	(xr, yr) = intersection(xp, xq, yp_pos, yq_pos)
	sympy.pprint((xr, yr))
	print "============="
	msg = "press enter to continue"
	raw_input(msg)

	xp = 1
	yp_pos = True
	print """
the intersection of the tangent line at x = %s (%s y) with the curve in reduced
form

""" % (xp, "positive" if yp_pos else "negative")

	xq = xp
	yq_pos = yp_pos
	(xr, yr) = intersection(xp, xq, yp_pos, yq_pos)
	print (xr.evalf(decimal_places), yr.evalf(decimal_places))
	print "============="
	raw_input(msg)

	yp_pos = True
	print """
the equation of the tangent line which passes through x = xp (%s y) on the curve

""" % "positive" if yp_pos else "negative"

	yq_pos = yp_pos
	(x, xp) = sympy.symbols("x xp")
	yp = y_ec(xp, yp_pos)
	m = slope(xp, xp, yp_pos, yq_pos)
	print "y = "
	print
	sympy.pprint(y_line(x, xp, yp, m))
	print "============="
	raw_input(msg)

	print """
the equation of the bitcoin eliptic curve

"""

	print "y = "
	print
	sympy.pprint(y_ec(sympy.symbols("x"), yp_pos = True))
	print
	print
	print "and y = "
	print
	sympy.pprint(y_ec(sympy.symbols("x"), yp_pos = False))
	print "============="
	raw_input(msg)

	xp = 15
	yp_pos = True
	print """
plot the bitcoin eliptic curve and visually check that P + P + P + P = 2P + 2P
using xp = %s (%s y)
""" % (xp, "positive" if yp_pos else "negative")

	# first calculate the rightmost x coordinate for the curve
	(x2p, y2p) = intersection(xp, xp, yp_pos, yp_pos)
	y2p = -y2p # point is mirrored about the x-axis
	y2p_pos = True if y2p >= 0 else False

	(x3p, y3p) = intersection(xp, x2p, yp_pos, y2p_pos)
	y3p = -y3p # point is mirrored about the x-axis
	y3p_pos = True if y3p >= 0 else False

	(x4p, y4p) = intersection(xp, x3p, yp_pos, y3p_pos)
	y4p = -y4p # point is mirrored about the x-axis

	init_plot_ec(max(xp, xp, x2p, x3p, x4p) + 2)
	plot_add(xp, xp, "P", "P", "2P", yp_pos, yp_pos, color = "r")
	plot_add(xp, x2p, "P", "2P", "3P", yp_pos, y2p_pos, color = "c")
	plot_add(xp, x3p, "P", "3P", "4P", yp_pos, y3p_pos, color = "g")
	plot_add(x2p, x2p, "2P", "2P", "4P", y2p_pos, y2p_pos, color = "y")
	finalize_plot_ec()
	print "============="
	raw_input(msg)

	print """
calculate the intersection of the curve with P + P + P + P and check that it is
equal to the intersection of the curve with 2P + 2P

"""

	# use xp, yp_pos from the previous test (easier to visualize)
	# P + P + P + P
	print "P + P + P + P = (%s, %s)" % (x4p, y4p)
	
	# 2P + 2P
	#(x2p_plus_2p, y2p_plus_2p) = intersection(x2p, x2p, y2p_pos, y2p_pos)
	(x2p_plus_2p, y2p_plus_2p) = intersection(x2p, x2p, y2p_pos, y2p_pos)
	print
	print "2P + 2P = (%s, %s)" % (x2p_plus_2p, -y2p_plus_2p)
	print "============="
	raw_input(msg)

	print """
calculate the intersection of the curve with P + P + P + P for an arbitrary P of
(xp, yp) and check that it is equal to the intersection of the curve with
2P + 2P

"""

	(xa, xb, xc, xd, x2b) = sympy.symbols("xa xb xc xd x2b")
	(ya, yb, yc, yd, y2b) = sympy.symbols("ya yb yc yd y2b")
	(ma, mab, mac, mb) = sympy.symbols("ma mab mac mb")

	# starting point. ya_pos = above x-axis, not ya_pos = below x-axis
	ya_pos = False
	(xb, yb) = intersection(xa, xa, ya_pos, ya_pos)
	# point b is mirrored about the x-axis
	yb = -yb
	yb_pos = True if yb >= 0 else False

	(xc, yc) = intersection(xa, xb, ya_pos, yb_pos)
	# point c is mirrored about the x-axis
	yc = -yc
	yc_pos = True if yc >= 0 else False

	(xd, yd) = intersection(xa, xc, ya_pos, yc_pos)
	# point d is mirrored about the x-axis
	yd = -yd
	yd_pos = True if yd >= 0 else False

	print "xd:"
	sympy.pprint(xd.simplify())

	(x2b, y2b) = intersection(xb, xb, yb_pos, yb_pos)
	# point 2b is mirrored about the x-axis
	y2b = -y2b
	print "x2b:"
	sympy.pprint(x2b.simplify())
	exit()




	(xa, xb, xc, xd, x2b) = sympy.symbols("xa xb xc xd x2b")
	(ya, yb, yc, yd, y2b) = sympy.symbols("ya yb yc yd y2b")
	(ma, mab, mac, mb) = sympy.symbols("ma mab mac mb")

	# starting point. ya_pos = above x-axis, not ya_pos = below x-axis
	ya_pos = False

	ya = y_ec(xa, ya_pos)
	ma = slope(xa, xa, ya_pos, ya_pos)
	#ma = (3 * xa**2) / (2 * ya)
	sympy.pprint(ma.simplify())
	exit()

	xb = sympy.sympify("ma**2 - (2 * xa)")
	yb = ma * (xb - xa) + ya
	# point b is mirrored about the x-axis
	yb = -yb
	mab = (yb - ya) / (xb - xa)

	xc = mab**2 - xa - xb
	# the slope from (xa, ya) to (xc, yc) also passes through (xb, -yb)
	yc = mab * (xc - xa) + ya
	# point c is mirrored about the x-axis
	yc = -yc
	mac = (yc - ya) / (xc - xa)

	xd = mac**2 - xa - xc
	# the slope from (xa, ya) to (xd, yd) also passes through (xc, -yc)
	yd = mac * (xd - xa) + ya
	yd = -yd

	print "xd:"
	sympy.pprint(xd.simplify())

	mb = (3 * xb**2) / (2 * yb)
	x2b = mb**2 - (2 * xb)
	y2b = mb * (x2b - xb) + yb
	# point 2b is mirrored about the x-axis
	y2b = -y2b
	print "x2b:"
	sympy.pprint((x2b - xd).simplify())

	# keeps the script from terminating, and therefore keeps all plot windows
	# from closing
	raw_input("press enter to exit")
