# output from `./ec_poly.py -m`


the intersection of the tangent line at x = 1 (positive y) with the curve in
non-reduced form:

![\left ( - \frac{55}{](d10c843bf1.png)

-------------

the intersection of the tangent line at x = 1 (positive y) with the curve in reduced
form:

`(-1.71875000000000000000000000000, 1.38659220373299553612978074131)`

-------------

the equation of the tangent line which passes through x = xp (positive y) on the
curve:

`y = `![\frac{3 xp^{2} \left](7625e1c20a.png)

-------------

the equation of the bitcoin elliptic curve:

`y = `![\sqrt{x^{3} + 7}](8ec0febd09.png)


and `y = `![- \sqrt{x^{3} + 7}](bc02a1067b.png)

-------------

plot the bitcoin elliptic curve and visually check that p + p + p + p = 2p + 2p
using xp = 10 (positive y):

![graph1](graph1.png)

-------------

calculate the intersection of the curve with p + p + p + p and check that it is
equal to the intersection of the curve with 2p + 2p:

p + p + p + p = `(-25983597172720/20434333412807, 205390966891466617199*sqrt(1007)/2931267467590684346699)`

2p + 2p = `(-25983597172720/20434333412807, 205390966891466617199*sqrt(1007)/2931267467590684346699)`

-------------

calculate the intersection of the curve with p + p + p + p for an arbitrary p of
`(xp, yp)` and check that it is equal to the intersection of the curve with
2p + 2p

x @ p + p + p + p:
![\frac{xp \left(xp^{1](fbfa192881.png)

y @ p + p + p + p:
![\frac{xp^{24} + 8624](728d4bd2c0.png)

x @ 2p + 2p:
![\frac{xp \left(xp^{1](fbfa192881.png)

y @ 2p + 2p:
![\frac{xp^{24} + 8624](728d4bd2c0.png)

should be 0 if x @ p + p + p + p = x @ 2p + 2p:
![0](b6589fc6ab.png)

should be 0 if y @ p + p + p + p = y @ 2p + 2p:
![0](b6589fc6ab.png)

-------------

plot the bitcoin elliptic curve and add point xp = 10 (positive y) to itself 7 times:

![graph2](graph2.png)

-------------

visually demonstrate the functionality of a master public/private key:

TODO

-------------
