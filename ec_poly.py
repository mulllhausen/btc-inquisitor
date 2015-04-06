#!/usr/bin/env python2.7

"""
functions related to plotting and calculating points on bitcoin's ecdsa
polynomial (secp256k1): y^2 = x^3 + 7

this file is standalone - it is just for understanding concepts, not used for
calculating real public or private keys.
"""

import numpy as np
import matplotlib.pyplot as plt

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
	of xp
	"""
	if string:
		return "%s(%s^3 + 7)^0.5" % ("" if yp_pos else "-", brackets(xp))
	else:
		y = (xp**3 + 7)**0.5
		return y if yp_pos else -y

def y_line(xr, xp, yp, m, string = False):
	"""
	return either the value of y at point x = xr, or the line equation for y in
	terms of xr
	"""
	if string:
		return "%s(%s - %s) + %s" % (
			brackets(m), brackets(xr), brackets(xp), brackets(yp)
		)
	else:
		return m * (xr - xp) + yp

def slope(xp, xq, yp_pos, yq_pos, string = False):
	"""return the equation of the slope which passes through points xp and xq"""
	if xp == xq:
		# when both points are on top of each other then we need to find the
		# tangent slope (the differential at xp)
		return tan_slope(xp, yp_pos, string = string)
	else:
		return non_tan_slope(xp, xq, yp_pos, yq_pos, string = string)

def tan_slope(xp, yp_pos, string = False):
	"""calculate the slope of the tangent to curve y^2 = x^3 + 7 at xp"""
	if string:
		xp = brackets(xp)
		return "3(%s^2) / (2(%s))" % (xp, y_ec(xp, yp_pos, string = True))
	else:
		return (3 * xp**2) / (2 * y_ec(xp, yp_pos))

def non_tan_slope(xp, xq, yp_pos, yq_pos, string = False):
	"""
	calculate the slope of the line that passes through p and q on curve
	y^2 = x^3 + 7
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
	with the curve
	"""
	yp = y_ec(xp, yp_pos, string = string)
	m = slope(xp, xq, yp_pos, yq_pos, string = string)
	xr = x_third_root(m, xp, xq, string = string)
	return (xr, y_line(xr, xp, yp, m, string = string))

def x_third_root(m, xp, xq, string = False):
	if string:
		if xp == xq:
			# simplify a bit
			return "(%s)^2 - 2(%s)" % (m, xp)
		else:
			return "(%s)^2 - %s - %s" % (m, brackets(xp), brackets(xq))
	else:
		return m**2 - xp - xq

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
def init_plot_ec(x_max = 4):
	"""
	initialize the eliptic curve plot - create the figure and plot the curve but
	do not put any multiplication lines on it yet and don't show it yet
	"""
	global plt, interval
	# the smallest x value on the curve is -cuberoot(7)
	x_min = -(7**(1 / 3.0))
	x = np.linspace(x_min, x_max, 1000)
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
	# the line between the two points upto the intersection with the curve. its
	# possible for the intersection to fall between p and q
	(xr, yr) = intersection(xp, xq, yp_pos, yq_pos)
	yp = y_ec(xp, yp_pos)
	x_min = min(xp, xq, xr)
	x_max = max(xp, xq, xr)
	x = np.linspace(x_min, x_max, 1000)
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
	y = np.linspace(yr, -yr, 2)
	x = np.linspace(xr, xr, 2)
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
	x2p = "(1024(sqrt(8) + sqrt(63001 / 32768))^2 / 7569 + (23 / 32))"
	print "reducing, P + P + P = (%s, %s)" % (x2p, y2p)

	(x4p, y4p) = intersection(xp, x3p, yp_pos, y3p_pos, string = True)
	#(x4p_val, y4p_val) = intersection(xp, x3p_val, yp_pos, y3p_pos)
	#y4p_val = -y4p_val # point is mirrored about the x-axis
	y4p = "-%s" % y4p # point is mirrored about the x-axis
	print "P + P + P + P = (%s, %s)" % (x4p, y4p)

	(x2p_plus_2p, y2p_plus_2p) = intersection(
		x2p, x2p, y2p_pos, y2p_pos, string = True
	)
	y2_plus_2p = "-(%s)" % y2p_plus_2p # point is mirrored about the x-axis
	print "2P + 2P = (%s, %s)" % (x2p_plus_2p, y2p_plus_2p)

	print "============="
	# keeps the script from terminating, and therefore keeps all plot windows
	# from closing
	plt.show()
