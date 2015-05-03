## investigating the bitcoin elliptic curve

output from `./btc-inquisitor/ec_poly.py -m`

the equation of the bitcoin elliptic curve is as follows:

![y^2 = x^3 + 7](ca1362ad69.png)

this equation is called `secp256k1` and looks like this:

![secp256k1](secp256k1.png)

### lets have a look at how elliptic curve point addition works...

to add two points on the elliptic curve, just draw a line through them and find the third intersection with the curve, then mirror this third point about the `x`-axis. for example, adding point `p` to point `q`:

![point_addition1](point_addition1.png)

note that the third intersection with the curve can also lie between the points being added:

![point_addition2](point_addition2.png)

try moving point `q` towards point `p` along the curve:

![point_addition3](point_addition3.png)

clearly as `q` approaches `p`, the line between `q` and `p` approaches the tangent at `p`. and at `q = p` this line *is* the tangent. so a point can be added to itself (`p + p`, ie `2p`) by finding the tangent to the curve at that point and the third intersection with the curve:

![point_doubling1](point_doubling1.png)

ok, but so what? when you say 'add points on the curve' is this just fancy mathematical lingo, or does this form of addition work like regular addition? for example does `p + p + p + p = 2p + 2p` on the curve?

to answer that, lets check with `p` at `x = 10` in the top half of the curve:

![4p1](4p1.png)

notice how the tangent to `2p` and the line through `p` and `3p` both result in the same intersection with the curve. lets zoom in to check:

![4p1_zoom](4p1_zoom.png)

ok they sure seem to converge on the same point, but maybe `x = 10` is just a special case? does point addition work for other values of `x`?

lets try `x = 4` in the bottom half of the curve:

![4p2](4p2.png)

so far so good. zooming in:

![4p2_zoom](4p2_zoom.png)

cool. lets do one last check using point `x = 3` in the top half of the curve:

![4p3](4p3.png)

well, this point addition on the bitcoin elliptic curve certainly works in the graphs. but what if the graphs are innaccurate? maybe the point addition is only approximate and the graphs do not display the inaccuracy...

a more accurate way of testing whether point addition really does work would be to compute the `x` and `y` coordinates at point `p + p + p + p` and also compute the `x` and `y` coordinates at point `2p + 2p` and see if they are identical. lets check for `x = 10` and y in the top half of the curve:

`p + p + p + p = (-25983597172720/20434333412807, 205390966891466617199*sqrt(1007)/2931267467590684346699)`

`2p + 2p = (-25983597172720/20434333412807, 205390966891466617199*sqrt(1007)/2931267467590684346699)`

cool! clearly they are identical :) however lets check the more general case where `x` at point `p` is a variable in the bottom half of the curve:

at `p + p + p + p`, `x` is computed as:

![x_{(p+p+p+p)} = \fra](c709765967.png)

and `y` is computed as:

![y_{(p+p+p+p)} = \fra](bc84bd5d14.png)

at `2p + 2p`, `x` is computed as:

![x_{(2p+2p)} = \frac{](dfff8fba0a.png)

and `y` is computed as:

![y_{(2p+2p)} = \frac{](985d81f486.png)

compare these results and you will see that that they are identical.this means that multiplication of points on the bitcoin elliptic curve really does work the same way as regular multiplication!


--------------------------------------------------------------------------------


TODO - subtraction, division, master public key, signatures

