from numpy import exp as np_exp
from numpy import linspace as np_linspace
from numpy import median as np_median
from numpy import column_stack as np_column_stack
from numpy import abs as np_abs
from scipy.integrate import simps # to calculate the area
from scipy.optimize import curve_fit
from shapely.geometry import LineString

def sigmoid_activ(x, L ,x0, k, b):
    y = L / (1 + np_exp(-k*(x-x0))) + b
    return (y)

def sigmoid_inactiv(x, L ,x0, k, b):
    y = (L) / (1 + np_exp(k*(x-x0))) + b
    return (y)

def activation_curve(voltage_active, y_activ, voltage_inactive, y_inactiv, samples = 500):
    x1 = voltage_active
    y1 = y_activ
    y2 = y_inactiv

    p01 = [max(y1)-min(y1), np_median(x1), 0.5, min(y1)] # this is an mandatory initial guess

    popt, pcov = curve_fit(sigmoid_activ, x1, y1, p01, method='dogbox')

    xn1 = np_linspace(x1.min(), x1.max(), samples ) # int( abs(x1.min())+abs(x1.max()))
    yn1 = sigmoid_activ(xn1, *popt)
    #yn1 = [y for y in yn1_pre if y>=0]

    return xn1, yn1

def inactivation_curve(voltage_active, y_activ, voltage_inactive, y_inactiv, samples = 500):
    x2 = voltage_inactive
    y1 = y_activ
    y2 = y_inactiv

    p02 = [max(y2)-min(y2), np_median(x2), 0.1, min(y2)] # this is an mandatory initial guess

    popt, pcov = curve_fit(sigmoid_inactiv, x2, y2, p02, method='dogbox')

    xn2_pre = np_linspace(x2.min(), x2.max(), samples ) # int( abs(x2.min())+abs(x2.max()))
    yn2_pre = sigmoid_inactiv(xn2_pre, *popt)
    
    yn2 = [y for y in yn2_pre if y>=0]
    idx_yn2_last_el = list(yn2).index(list(yn2)[-1])
    xn2 = xn2_pre[0:idx_yn2_last_el+1]

    return xn2, yn2

def calculate_area_under_curves(xn1, yn1, xn2, yn2, samples = 500):
    line_1 = LineString(np_column_stack((xn1, yn1)))
    line_2 = LineString(np_column_stack((xn2, yn2)))

    intersection = line_1.intersection(line_2)
    #print('intersection', intersection, ' intersection.x ', intersection.x, ' intersection.y ', intersection.y)
    #plt.plot(*intersection.xy, 'bo')

    idx1 = (np_abs(xn1-intersection.x)).argmin()
    idx2 = (np_abs(xn2-intersection.x)).argmin()

    #print(' xn1 = ', xn1[idx1], ' xn2 = ', xn2[idx2], ' yn1 = ', yn1[idx1], ' yn2 = ', yn2[idx2])
    
    idx_yn2_last_el = list(yn2).index(list(yn2)[-1])
    f1 = simps(yn1[0:idx1], xn1[0:idx1])
    f2 = simps(yn2[idx2:idx_yn2_last_el], xn2[idx2:idx_yn2_last_el])

    area = f1+f2
    print(f'Calculated area = {area}')
    return area, intersection, idx1, idx2
    


