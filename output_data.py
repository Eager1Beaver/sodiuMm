import pandas as pd

def outputExcel(output_path, 
                x1, y1, x2, y2, 
                xn1, yn1, xn2, yn2, 
                area, 
                verbose: int = 0) -> None:
    """
    outputs all data to xlsx
    """
    #curve_data = pd.concat([x1, y1, x2, y2, xn1, yn1, xn2, yn2], axis=0)
    #curve_dataT = curve_data.T
    df_x1 = pd.DataFrame([x1])
    df_y1 = pd.DataFrame([y1])
    df_x2 = pd.DataFrame([x2])
    df_y2 = pd.DataFrame([y2])

    df_xn1 = pd.DataFrame([xn1])
    df_yn1 = pd.DataFrame([yn1])
    df_xn2 = pd.DataFrame([xn2])
    df_yn2 = pd.DataFrame([yn2])

    curve_data = pd.concat([df_x1, df_y1, df_x2, df_y2, df_xn1, df_yn1, df_xn2, df_yn2], axis=0)
    curve_dataT = curve_data.T

    columns_names = ['EXP_voltage_activ', 'EXP_y_activ', 
                     'EXP_voltage_inactiv', 'EXP_y_inactiv',
                     'FIT_voltage_activ', 'FIT_y_activ',
                     'FIT_voltage_inactiv', 'FIT_y_inactiv']
    
    curve_dataT.columns = columns_names
    #curve_dataT.index.drop
    ###

    area_data = pd.DataFrame([area])
    area_data.columns = ['area under the curves']
    #area_data.index.drop

    #output_path = 'output_data.xlsx'
    if verbose in [1,2]: print(f'Data is saved to: {output_path}\n')
    with pd.ExcelWriter(output_path) as writer: 
        curve_dataT.to_excel(writer, sheet_name='output_curve_data', index=False)  
        area_data.to_excel(writer, sheet_name='output_area_data', index=False)
        #
    ###    