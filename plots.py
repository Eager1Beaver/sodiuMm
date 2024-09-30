import matplotlib.pyplot as plt

def pltBaseline_and_curves_and_area(x1,y1,x2,y2,
                                      xn1,yn1,xn2,yn2,
                                      idx1,idx2,
                                      intersection,
                                      samples=500):
    plt.plot(xn1,yn1, label='Activation, fit')
    plt.plot(x1,y1,'ro',label='Activation, exp')

    plt.plot(xn2,yn2, label='Inactivation, fit')
    plt.plot(x2,y2,'go',label='Inactivation, exp')

    plt.plot(*intersection.xy, 'bo')

    plt.fill_between(xn1[0:idx1], yn1[0:idx1], alpha=0.5)
    plt.fill_between(xn2[idx2:samples], yn2[idx2:samples], alpha=0.5)

    plt.legend()
    plt.grid()
    plt.show()
    ###