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

def y_ec(xp, pos = True, string = False):
	"""
	return either the value of y at point x = xp, or the equation for y in terms
	of xp
	"""
	if string:
		return "%s(%s^3 + 7)^0.5" % ("" if pos else "-", brackets(xp))
	else:
		y = (xp**3 + 7)**0.5
		return y if pos else -y

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

def slope(xp, xq, string = False):
	"""return the equation of the slope which passes through points xp and xq"""
	if xp == xq:
		# when both points are on top of each other then we need to find the
		# tangent slope (the differential at xp)
		return tan_slope(xp, string = string)
	else:
		return non_tan_slope(xp, xq, string = string)

def tan_slope(xp, string = False):
	"""calculate the slope of the tangent to curve y^2 = x^3 + 7 at xp"""
	if string:
		xp = brackets(xp)
		return "3(%s^2) / (2(%s))" % (xp, y_ec(xp, string = True))
	else:
		return (3 * xp**2) / (2 * (xp**3 + 7)**0.5)

def non_tan_slope(xp, xq, string = False):
	"""
	calculate the slope of the line that passes through p and q on curve
	y^2 = x^3 + 7
	"""
	if string:
		yp = y_ec(xp, string = True)
		yq = y_ec(xq, string = True)
		return "(%s - %s)/(%s - %s)" % (yp, yq, brackets(xp), brackets(xq))
	else:
		return (y_ec(xp) - y_ec(xq))/(xp - xq)

def intersection(xp, xq, string = False):
	"""
	calculate the intersection coordinates of the line through x = xp and x = xq
	with the curve
	"""
	yp = y_ec(xp, string = string)
	m = slope(xp, xq, string = string)
	xr = x_third_root(m, xp, xq, string = string)
	return (xr, y_line(xr, xp, yp, m, string = string))

def x_third_root(m, xp, xq, string = False):
	if string:
		if xp == xq:
			# simplify a bit
			return "(%s)^2 - 2(%s)" % (m, xp)
		else:
			return "(%s)^2 - %s - %s" % (m, xp, xq)
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
def init_plot_ec():
	"""
	initialize the eliptic curve plot - create the figure and plot the curve but
	do not put any multiplication lines on it yet and don't show it yet
	"""
	global plt, interval
	# the smallest x value on the curve is -cuberoot(7)
	x_min = -(7**(1 / 3.0))
	x_max = 4
	x = np.linspace(x_min, x_max, 1000)
	y_ = y_ec(x)
	plt.figure()
	plt.grid(True)
	# plot the eliptic curve in blue
	curve_color = "b"
	plt.plot(x, y_, curve_color)
	plt.plot(x, -y_, curve_color)

def add(xp, xq, p_name, q_name, p_plus_q_name, yp_pos = True, yq_pos = True):
	"""
	add two points on the curve. this involves plotting a line through both
	points and finding the third intersection with the curve, then mirroring
	that point about the x axis.
	"""
	# plot addition lines in red
	line_color = "r"

	# the line between the two points upto the intersection with the curve
	(xr, yr) = intersection(xp, xq)
	yp = y_ec(xp)
	x_max = xp if xp > xq else xq
	x_min = xr
	x = np.linspace(x_min, x_max, 1000)
	m = slope(xp, xq)
	y = y_line(x, xp, yp, m)
	plt.plot(x, y, line_color)
	plt.plot(xp, yp, "%so" % line_color)
	plt.text(xp - 0.1, yp + 0.5, p_name)
	if xp is not xq:
		yq = y_ec(xq)
		plt.plot(xq, yq, "%so" % line_color)
		plt.text(xq - 0.1, yq + 0.5, q_name)

	# the vertical line to the other side of the curve
	y = np.linspace(yr, -yr, 2)
	x = np.linspace(xr, xr, 2)
	plt.plot(x, y, "%s" % line_color)
	plt.plot(xr, -yr, "%so" % line_color)
	plt.text(xr - 0.1, 0.5 - yr, p_plus_q_name)

def finalize_plot_ec():
	global plt
	plt.show()

################################################################################
# end functions for plotting graphs
################################################################################

if __name__ == "__main__":
	print
	print """the intersection of the tangent line at x = 1 (positive y) with the curve in
non-reduced form"""
	xp = 1
	xq = xp
	print intersection(xp, xq, string = True)
	print """
--------------------------------------------------------------------------------
"""

	print """the intersection of the tangent line at x = 1 (positive y) with the curve in
reduced form"""
	xp = 1
	xq = xp
	print intersection(xp, xq, string = False)
	print """
--------------------------------------------------------------------------------
"""

	print """the equation of the line which passes through x = 1 (positive y) on the curve
and its intersection with the curve again"""
	xp = 1
	yp = y_ec(xp, string = True)
	m = slope(xp, xp, string = True)
	print "y = %s" % y_line("x", xp, yp, m, string = True)
	print """
--------------------------------------------------------------------------------
"""

	print """the equation of the bitcoin eliptic curve"""
	print "y = %s" % y_ec("x", pos = True, string = True)
	print "and y = %s" % y_ec("x", pos = False, string = True)
	print """
--------------------------------------------------------------------------------
"""

	print """plot the bitcoin eliptic curve and add two points on it"""
	init_plot_ec()
	add(1, 3, "P", "Q", "P+Q")
	finalize_plot_ec()
	print """
--------------------------------------------------------------------------------
"""
