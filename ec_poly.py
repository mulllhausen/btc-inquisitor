"""
functions related to plotting and calculating points on bitcoin's ecdsa
polynomial (secp256k1): y^2 = x^3 + 7
"""

import numpy as np
import matplotlib.pyplot as plt

def find_ints_on_curve(max_x):
	"""hint - there aren't any below x = 10,000,000"""
	x = 0
	while x <= max_x:
		mid_x = x**3 + 7
		y = mid_x**0.5
		y_int = int(y)
		recalc_mid_x = y_int**2
		if recalc_mid_x == mid_x:
		#if y_int == y: # don't use this - it is not correct
			print "x = ", x, "y = ", y
		x += 1

def y(xp, pos = True):
	y = (xp**3 + 7)**0.5
	return y if pos else -y

def yr3(xr3, xp, yp, m):
	"""
	the line intersects the curve on its 3rd root - the other two are known.
	for point doubling there is a double root at x = xp, or for point addition
	there is a root at x = xp and a root at x = xq.
	"""
	return m * (xr3 - xp) + yp

def yr3_str(xr3, xp, yp, m):
	return "(%s)(%s - %s) + %s" % (m, xr3, xp, yp)

def y_str(x):
	return "(%s^3 + 7)^0.5" % x

def tan_slope(x):
	"""calculate the slope of the tangent to curve y^2 = x^3 + 7 at x"""
	return (3 * x**2) / (2 * (x**3 + 7)**0.5)

def tan_slope_str(x):
	return "3%s^2 / (2(%s^3 + 7)^0.5)" % (x, x)

def non_tan_slope(xp, xq):
	"""
	calculate the slope of the line that passes through p and q on curve
	y^2 = x^3 + 7
	"""
	return (y(xp) - y(xq))/(xp - xq)

def non_tan_slope_str(xp, xq):
	yp = y_str(xp)
	yq = y_str(xq)
	return "(%s - %s)/(%s - %s)" % (yp, yq, xp, xq)

def slope_str(xp, xq):
	"""return the equation of the slope which passes through points xp and xq"""
	if xp == xq:
		# when both points are on top of each other then we need to find the
		# tangent slope (the differential at xp)
		return tan_slope_str(xp)
	else:
		return non_tan_slope_str(xp, xq)

def line_str(xp, xq):
	"""return the equation of the line which passes through points xp and xq"""
	m_str = slope_str(xp, xq)
	yp = y_str(xp)
	return "y = (%s)(x - %s) + %s" % (m_str, xp, yp)

def intersection(xp, xq):
	"""
	calculate the intersection coordinates of the line through x = xp and x = xq
	with the curve
	"""
	yp = y(xp)
	if xp == xq:
		m = tan_slope(xp)
		xr3 = m**2 - (2 * xp)
	else:
		m = non_tan_slope(xp, xq)
		xr3 = m**2 - xp - xq
	return (xr3, yr3(xr3, xp, yp, m))

def intersection_str(xp, xq):
	"""
	return the equations for the intersection coordinates of the line through
	x = xp and x = xq with the curve
	"""
	yp = y_str(xp)
	if xp == xq:
		m_str = tan_slope_str(xp)
		xr3_str = "(%s)^2 - 2(%s)" % (m_str, xp)
	else:
		m_str = non_tan_slope_str(xp, xq)
		xr3_str = "(%s)^2 - %s - %s" % (m_str, xp, xq)
	return (xr3_str, yr3_str(xr3_str, xp, yp, m_str))

def plot_ec():
	# the smallest x value on the curve is -cuberoot(7)
	x_min = -(7**(1 / 3.0))
	x = np.arange(x_min, 4, 0.05)
	y_ = y(x)
	plt.figure()
	plt.plot(x, y_, "b")
	plt.plot(x, -y_, "b")
	plt.grid(True)
	plt.show()
