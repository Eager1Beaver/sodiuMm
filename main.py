from input_data import inputExcel
from pipeline import *
from plots import *
from output_data import *

from gui import MainWindow

def main_func():
    verbose = 1
    samples = 1000 # should be consistent
    input_path = app.setInputDataPath()
    output_path = app.setOutputDataPath()

    voltage_active, y_activ, voltage_inactive, y_inactiv = inputExcel(input_path, verbose=verbose)

    xn1, yn1 = activation_curve(voltage_active, y_activ, voltage_inactive, y_inactiv, samples = samples)

    xn2, yn2 = inactivation_curve(voltage_active, y_activ, voltage_inactive, y_inactiv, samples = samples)

    area, intersection, idx1, idx2 = calculate_area_under_curves(xn1, yn1, xn2, yn2, samples = samples)

    x1 = voltage_active
    x2 = voltage_inactive
    y1 = y_activ
    y2 = y_inactiv

    pltBaseline_and_curves_and_area(x1,y1,x2,y2,
                                      xn1,yn1,xn2,yn2,
                                      idx1, idx2,
                                      intersection,
                                      samples=samples)
    ###

    outputExcel(output_path, 
                x1, y1, x2, y2, 
                xn1, yn1, xn2, yn2, 
                area, 
                verbose = verbose)
    print('Output saved\n')

    return 0

if __name__ == '__main__':
    print('Program started\n\n')
    print(
        '        #####################################################################\n\
        #                                                                   #\n\
        #    ___  ___  _______   ___       ___       ________  ___          #\n\
        #   |\  \|\  \|\  ___ \ |\  \     |\  \     |\   __  \|\  \         #\n\
        #   \ \  \\\  \ \   __/|\ \  \    \ \  \    \ \  \|\  \ \  \         #\n\
        #    \ \   __  \ \  \_|/_\ \  \    \ \  \    \ \  \\\  \ \  \        #\n\
        #     \ \  \ \  \ \  \_|\ \ \  \____\ \  \____\ \  \\\  \ \__\       #\n\
        #      \ \__\ \__\ \_______\ \_______\ \_______\ \_______\|__|      #\n\
        #       \|__|\|__|\|_______|\|_______|\|_______|\|_______|   ___    #\n\
        #                                                           |\__\   #\n\
        #                                                           \|__|   #\n\
        #                                                                   #\n\
        #####################################################################\n\
')
    print(f'\nGlobal parameters:\n\
        1) Verbose --- detalization of output info\n\
        \t 0 --- silent\n\
        \t 1 --- major plots and messages\n\
        \t 2 --- all plots and messages\n')
    ###
    
    app = MainWindow(main_func)
    app.mainloop()
    #
    print('Program finished\n')
