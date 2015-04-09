#!/usr/bin/env python2.7

"""
functions related to plotting and calculating points on bitcoin's ecdsa
polynomial (secp256k1): y^2 = x^3 + 7

this file is standalone - it is just for understanding concepts, not used for
calculating real public or private keys.
"""
import sympy

################################################################################
# begin equation and calculation functions
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

def y_ec(xp, yp_pos, string = False):
	"""
	return either the value of y at point x = xp, or the equation for y in terms
	of xp. xp defines the scalar value of y but does not specify whether the
	result is in the top or the bottom half of the curve. the yp_pos input gives
	this:
	yp_pos == True means yp is a positive value: y = +(x^3 + 7)^0.5
	yp_pos == False means yp is a negative value: y = -(x^3 + 7)^0.5
	"""
	if string:
		return "%s(%s^3 + 7)^0.5" % ("" if yp_pos else "-", brackets(xp))
	else:
		y = (xp**3 + 7)**0.5
		return y if yp_pos else -y

def y_line(x, xp, yp, m, string = False):
	"""
	return either the value of y at point x = xr, or the line equation for y in
	terms of x:
	y = mx + c
	ie yp = m(xp) + c
	ie c = yp - m(xp)
	ie y = mx + yp - m(xp)
	ie y = m(x - xp) + yp
	"""
	if string:
		return "%s(%s - %s) + %s" % (
			brackets(m), brackets(x), brackets(xp), brackets(yp)
		)
	else:
		return m * (x - xp) + yp

def slope(xp, xq, yp_pos, yq_pos, string = False):
	"""return the equation of the slope which passes through points xp and xq"""
	if xp == xq:
		# when both points are on top of each other then we need to find the
		# tangent slope at xp
		return tan_slope(xp, yp_pos, string = string)
	else:
		return non_tan_slope(xp, xq, yp_pos, yq_pos, string = string)

def tan_slope(xp, yp_pos, string = False):
	"""
	calculate the slope of the tangent to curve y^2 = x^3 + 7 at xp.
	the curve can be written as y = (x^3 + 7)^0.5 (positive and negative) and
	the slope of the tangent is the derivative:
	m = dy/dx = (0.5(x^3 + 7)^-0.5)(3x^2)
	m = 3x^2 / (2(x^3 + 7)^0.5)
	m = 3x^2 / 2y
	"""
	if string:
		xp = brackets(xp)
		return "3(%s^2) / (2(%s))" % (xp, y_ec(xp, yp_pos, string = True))
	else:
		return (3 * xp**2) / (2 * y_ec(xp, yp_pos))

def non_tan_slope(xp, xq, yp_pos, yq_pos, string = False):
	"""
	calculate the slope of the line that passes through p and q (two different
	points - hence they are not a tangent) on curve y^2 = x^3 + 7. this is just
	the y-step over the x-step - ie m = (yp - yq) / (xp - xq)
	"""
	if string:
		yp = y_ec(xp, yp_pos, string = True)
		yq = y_ec(xq, yq_pos, string = True)
		return "(%s - %s)/(%s - %s)" % (yp, yq, brackets(xp), brackets(xq))
	else:
		return (y_ec(xp, yp_pos) - y_ec(xq, yq_pos))/(xp - xq)

def intersection(xp, xq, yp_pos, yq_pos, string = False):
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
	yp = y_ec(xp, yp_pos, string = string)
	m = slope(xp, xq, yp_pos, yq_pos, string = string)

	if string:
		if xp == xq:
			# simplify a bit
			r3 = "(%s)^2 - 2(%s)" % (m, xp)
		else:
			r3 = "(%s)^2 - %s - %s" % (m, brackets(xp), brackets(xq))
	else:
		r3 = m**2 - xp - xq

	return (r3, y_line(r3, xp, yp, m, string = string))

def brackets(x):
	"""
	put brackets around the variable to make it unambiguous when substituting
	into string representations of equations
	"""
	if (
		isinstance(x, str) and
		len(x) > 1
	):
		x = "(%s)" % x
	return x

################################################################################
# end equation and calculation functions
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
	do not put any multiplication lines on it yet and don't show it yet
	"""
	global plt, interval
	# the smallest x value on the curve is -cuberoot(7)
	x_min = -(7**(1 / 3.0))
	x = numpy.linspace(x_min, x_max, curve_steps)
	y_ = y_ec(x, yp_pos = True)
	plt.figure()
	plt.grid(True)
	# plot the eliptic curve in blue
	color = "b"
	plt.plot(x, y_, color)
	plt.plot(x, -y_, color)
	plt.ylabel("y")
	plt.xlabel("x")
	plt.title("secp256k1: y^2 = x^3 + 7")

def plot_add(
	xp, xq, p_name, q_name, p_plus_q_name, yp_pos, yq_pos, color = "r"
):
	"""
	add two points on the curve. this involves plotting a line through both
	points and finding the third intersection with the curve, then mirroring
	that point about the x axis.
	"""
	# the line between the two points upto the intersection with the curve. note
	# that it is possible for the intersection to fall between p and q
	(xr, yr) = intersection(xp, xq, yp_pos, yq_pos)
	yp = y_ec(xp, yp_pos)
	x_min = min(xp, xq, xr)
	x_max = max(xp, xq, xr)
	x = numpy.linspace(x_min, x_max, 2)
	m = slope(xp, xq, yp_pos, yq_pos)
	y = y_line(x, xp, yp, m)
	plt.plot(x, y, color)
	plt.plot(xp, yp, "%so" % color)
	plt.text(xp - 0.1, yp + 0.5, p_name)
	if xp is not xq:
		yq = y_ec(xq, yq_pos)
		plt.plot(xq, yq, "%so" % color)
		plt.text(xq - 0.1, yq + 0.5, q_name)

	# the vertical line to the other half of the curve
	y = numpy.linspace(yr, -yr, 2)
	x = numpy.linspace(xr, xr, 2)
	plt.plot(x, y, "%s" % color)
	plt.plot(xr, -yr, "%so" % color)
	plt.text(xr - 0.1, 0.5 - yr, p_plus_q_name)

def finalize_plot_ec():
	global plt
	plt.show(block = False)

################################################################################
# end functions for plotting graphs
################################################################################

if __name__ == "__main__":

	print """
the intersection of the tangent line at x = 1 (positive y) with the curve in
non-reduced form
"""
	xp = 1
	xq = xp
	yp_pos = True
	yq_pos = yp_pos
	print intersection(xp, xq, yp_pos, yq_pos, string = True)
	print "============="
	msg = "press enter to continue"
	raw_input(msg)

	print """
the intersection of the tangent line at x = 1 (positive y) with the curve in
reduced form
"""
	xp = 1
	xq = xp
	yp_pos = True
	yq_pos = yp_pos
	print intersection(xp, xq, yp_pos, yq_pos, string = False)
	print "============="
	raw_input(msg)

	print """
the equation of the tangent line which passes through x = 1 (positive y) on the
curve and its intersection with the curve again
"""
	xp = 1
	yp_pos = True
	yq_pos = yp_pos
	yp = y_ec(xp, yp_pos, string = True)
	m = slope(xp, xp, yp_pos, yq_pos, string = True)
	print "y = %s" % y_line("x", xp, yp, m, string = True)
	print "============="
	raw_input(msg)

	print """
the equation of the bitcoin eliptic curve
"""
	print "y = %s" % y_ec("x", yp_pos = True, string = True)
	print "and y = %s" % y_ec("x", yp_pos = False, string = True)
	print "============="
	raw_input(msg)

	print """
plot the bitcoin eliptic curve and check that P + P + P + P = 2P + 2P
"""
	xp = 15
	yp_pos = False

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
calculate the intersection of the curve with P + P + P + P (in reduced form) and
check that it is equal to the intersection of the curve with 2P + 2P (also in
reduced form)
"""
	# use xp, yp_pos from the previous test (easier to visualize)
	# P + P + P + P
	print "P + P + P + P = (%s, %s)" % (x4p, y4p)
	
	# 2P + 2P
	(x2p_plus_2p, y2p_plus_2p) = intersection(x2p, x2p, y2p_pos, y2p_pos)
	print "2P + 2P = (%s, %s)" % (x2p_plus_2p, -y2p_plus_2p)
	print "============="
	raw_input(msg)

	print """
calculate the intersection of the curve with P + P + P + P (in non-reduced form)
and check that it is equal to the intersection of the curve with 2P + 2P (also
in non-reduced form)
"""
	# use a nice simple number here to keep 4P as simple as possible
	xp = 1
	yp_pos = True

	(x2p, y2p) = intersection(xp, xp, yp_pos, yp_pos, string = True)
	(x2p_val, y2p_val) = intersection(xp, xp, yp_pos, yp_pos)
	y2p_val = -y2p_val # point is mirrored about the x-axis
	y2p = "-(%s)" % y2p # point is mirrored about the x-axis
	y2p_pos = True if y2p_val >= 0 else False
	print "P + P = (%s, %s)" % (x2p, y2p)
	"""
	the result for xp = 1 is P + P = ((3(1^2) / (2((1^3 + 7)^0.5)))^2 - 2(1), -((3(1^2) / (2((1^3 + 7)^0.5)))(((3(1^2) / (2((1^3 + 7)^0.5)))^2 - 2(1)) - 1) + ((1^3 + 7)^0.5)))
	we can reduce the x coordinate so that the next equation is shorter (there
	is no need to reduce the y coordinate since it is not used to calculate the
	next equation)...
	P + P = ((3 / (2(8^0.5)))^2 - 2, y2p)
	P + P = ((9 / (4(8))) - 2, y2p)
	P + P = ((9 / 32) - 2, y2p)
	P + P = (-55 / 32, y2p)
	"""
	# now use this reduced value to keep the next result shorter
	x2p = "-55 / 32"
	print "reducing, P + P = (%s, %s)" % (x2p, y2p)

	(x3p, y3p) = intersection(xp, x2p, yp_pos, y2p_pos, string = True)
	(x3p_val, y3p_val) = intersection(xp, x2p_val, yp_pos, y2p_pos)
	y3p_val = -y3p_val # point is mirrored about the x-axis
	y3p = "-(%s)" % y3p # point is mirrored about the x-axis
	y3p_pos = True if y3p_val >= 0 else False
	print "P + P + P = (%s, %s)" % (x3p, y3p)
	"""
	the result for xp = 1 is P + P + P = ((((1^3 + 7)^0.5 - -((-55 / 32)^3 + 7)^0.5)/(1 - (-55 / 32)))^2 - 1 - -55 / 32, -((((1^3 + 7)^0.5 - -((-55 / 32)^3 + 7)^0.5)/(1 - (-55 / 32)))(((((1^3 + 7)^0.5 - -((-55 / 32)^3 + 7)^0.5)/(1 - (-55 / 32)))^2 - 1 - -55 / 32) - 1) + ((1^3 + 7)^0.5)))
	we can reduce the x coordinate so that the next equation is shorter (there
	is no need to reduce the y coordinate since it is not used to calculate the
	next equation)...
	P + P + P = (((8^0.5 - -((-55 / 32)^3 + 7)^0.5)/(1 - (-55 / 32)))^2 - 1 - -(55 / 32), y3p)
	P + P + P = (((sqrt(8) + sqrt((-166375 / 32768) + 7))/(1 + (55 / 32)))^2 - 1 + (55 / 32), y3p)
	P + P + P = ((sqrt(8) + sqrt(63001 / 32768))^2 / (7569 / 1024) + (23 / 32), y3p)
	P + P + P = (1024(sqrt(8) + sqrt(63001 / 32768))^2 / 7569 + (23 / 32), y3p)
	"""
	# now use this reduced value to keep the next result shorter
	x3p = "(1024(sqrt(8) + sqrt(63001 / 32768))^2 / 7569 + (23 / 32))"
	print "reducing, P + P + P = (%s, %s)" % (x3p, y3p)

	(x4p, y4p) = intersection(xp, x3p, yp_pos, y3p_pos, string = True)
	#(x4p_val, y4p_val) = intersection(xp, x3p_val, yp_pos, y3p_pos)
	#y4p_val = -y4p_val # point is mirrored about the x-axis
	y4p = "-%s" % y4p # point is mirrored about the x-axis
	print "P + P + P + P = (%s, %s)" % (x4p, y4p)
	"""
	the result for xp = 1 is P + P + P + P = ((((1^3 + 7)^0.5 - -(((1024(sqrt(8) + sqrt(63001 / 32768))^2 / 7569 + (23 / 32)))^3 + 7)^0.5)/(1 - ((1024(sqrt(8) + sqrt(63001 / 32768))^2 / 7569 + (23 / 32)))))^2 - 1 - ((1024(sqrt(8) + sqrt(63001 / 32768))^2 / 7569 + (23 / 32))), -(((1^3 + 7)^0.5 - -(((1024(sqrt(8) + sqrt(63001 / 32768))^2 / 7569 + (23 / 32)))^3 + 7)^0.5)/(1 - ((1024(sqrt(8) + sqrt(63001 / 32768))^2 / 7569 + (23 / 32)))))(((((1^3 + 7)^0.5 - -(((1024(sqrt(8) + sqrt(63001 / 32768))^2 / 7569 + (23 / 32)))^3 + 7)^0.5)/(1 - ((1024(sqrt(8) + sqrt(63001 / 32768))^2 / 7569 + (23 / 32)))))^2 - 1 - ((1024(sqrt(8) + sqrt(63001 / 32768))^2 / 7569 + (23 / 32)))) - 1) + ((1^3 + 7)^0.5))
	we can reduce the coordinates so that we can more easily compare it to the
	result of 2P + 2P
	P + P + P + P = (((8^0.5 + ((1024(sqrt(8) + sqrt(63001 / 32768))^2 / 7569 + (23 / 32))^3 + 7)^0.5)/(1 - ((1024(sqrt(8) + sqrt(63001 / 32768))^2 / 7569 + (23 / 32)))))^2 - 1 - ((1024(sqrt(8) + sqrt(63001 / 32768))^2 / 7569 + (23 / 32))), -((8^0.5 + ((1024(sqrt(8) + sqrt(63001 / 32768))^2 / 7569 + (23 / 32))^3 + 7)^0.5)/(1 - ((1024(sqrt(8) + sqrt(63001 / 32768))^2 / 7569 + (23 / 32)))))((((8^0.5 + ((1024(sqrt(8) + sqrt(63001 / 32768))^2 / 7569 + (23 / 32))^3 + 7)^0.5)/(1 - (1024(sqrt(8) + sqrt(63001 / 32768))^2 / 7569 + (23 / 32))))^2 - 1 - (1024(sqrt(8) + sqrt(63001 / 32768))^2 / 7569 + (23 / 32))) - 1) + 8^0.5)
	P + P + P + P = (((sqrt(8) + sqrt((1024(sqrt(8) + sqrt(63001 / 32768))^2 / 7569 + (23 / 32))^3 + 7))/(1 - (1024(sqrt(8) + sqrt(63001 / 32768))^2 / 7569 + (23 / 32))))^2 - 1 - ((1024(sqrt(8) + sqrt(63001 / 32768))^2 / 7569 + (23 / 32))), -((sqrt(8) + sqrt((1024(sqrt(8) + sqrt(63001 / 32768))^2 / 7569 + (23 / 32))^3 + 7))/(1 - ((1024(sqrt(8) + sqrt(63001 / 32768))^2 / 7569 + (23 / 32)))))((((sqrt(8) + sqrt((1024(sqrt(8) + sqrt(63001 / 32768))^2 / 7569 + (23 / 32))^3 + 7))/(1 - (1024(sqrt(8) + sqrt(63001 / 32768))^2 / 7569 + (23 / 32))))^2 - 1 - (1024(sqrt(8) + sqrt(63001 / 32768))^2 / 7569 + (23 / 32))) - 1) + sqrt(8))
	"""
	x4p = "((sqrt(8) + sqrt((1024(sqrt(8) + sqrt(63001 / 32768))^2 / 7569 + (23 / 32))^3 + 7))/(1 - (1024(sqrt(8) + sqrt(63001 / 32768))^2 / 7569 + (23 / 32))))^2 - 1 - ((1024(sqrt(8) + sqrt(63001 / 32768))^2 / 7569 + (23 / 32)))"
	y4p = "-((sqrt(8) + sqrt((1024(sqrt(8) + sqrt(63001 / 32768))^2 / 7569 + (23 / 32))^3 + 7))/(1 - ((1024(sqrt(8) + sqrt(63001 / 32768))^2 / 7569 + (23 / 32)))))((((sqrt(8) + sqrt((1024(sqrt(8) + sqrt(63001 / 32768))^2 / 7569 + (23 / 32))^3 + 7))/(1 - (1024(sqrt(8) + sqrt(63001 / 32768))^2 / 7569 + (23 / 32))))^2 - 1 - (1024(sqrt(8) + sqrt(63001 / 32768))^2 / 7569 + (23 / 32))) - 1) + sqrt(8)"
	print "reducing, P + P + P + P = (%s, %s)" % (x4p, y4p)

	(x2p_plus_2p, y2p_plus_2p) = intersection(
		x2p, x2p, y2p_pos, y2p_pos, string = True
	)
	y2_plus_2p = "-(%s)" % y2p_plus_2p # point is mirrored about the x-axis
	print "2P + 2P = (%s, %s)" % (x2p_plus_2p, y2p_plus_2p)
	"""
	the result for xp = 1 is 2P + 2P =
	we can reduce the coordinates so that we can more easily compare it to the
	result of P + P + P + P
	2P + 2P = ((3((-55 / 32)^2) / (2(-(((-55 / 32))^3 + 7)^0.5)))^2 - 2(-55 / 32), (3((-55 / 32)^2) / (2(-(((-55 / 32))^3 + 7)^0.5)))(((3((-55 / 32)^2) / (2(-(((-55 / 32))^3 + 7)^0.5)))^2 - 2(-55 / 32)) - (-55 / 32)) + (-((-55 / 32)^3 + 7)^0.5))
	"""
	x2p_plus_2p = ""
	y2p_plus_2p = ""
	print "reducing, 2P + 2P = (%s, %s)" % (x2p_plus_2p, y2p_plus_2p)
	print "============="
	raw_input(msg)

	print """
simplify the equation for the intersection of the curve with P + P + P + P and
check that it is equal to the intersection of the curve with 2P + 2P
"""
	# detect the best form of pretty printing available
	sympy.init_printing()

	(xa, xb, xc, xd, x2b) = sympy.symbols("xa xb xc xd x2b")
	(ya, yb, yc, yd, y2b) = sympy.symbols("ya yb yc yd y2b")
	(ma, mab, mac, mb) = sympy.symbols("ma mab mac mb")

	# starting point. 1 = above x-axis, -1 = below x-axis
	ya_pos = -1

	ya = sympy.sqrt(xa**3 + 7)
	ma = (3 * xa**2) / (2 * ya)

	xb = ma**2 - (2 * xa)
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
	sympy.pprint(x2b.simplify())

	# keeps the script from terminating, and therefore keeps all plot windows
	# from closing
	plt.show()
