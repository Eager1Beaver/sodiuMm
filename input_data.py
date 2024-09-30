import pandas as pd

def inputExcel(input_path, verbose: int = 0):
    """
    input baseline data\n
    verbose: how much info to print
    """
    #file_name = 'data_7t'
    #cwd = os.getcwd()
    #input_path = cwd + '/' + file_name + '.csv'
    #data_df = pd.read_csv(input_path) # USER_DEFINED
    try:
        data_df = pd.read_excel(input_path, sheet_name='data')
    except:
        data_df = pd.read_csv(input_path)
    if verbose in [2]: print(f'Data loaded from: {input_path}\n')
    if verbose in [2]: print(f'Loaded data:\n{data_df.head()}\n')

    voltage_active = data_df[data_df.columns[0]].dropna()
    y_activ = data_df[data_df.columns[1]].dropna()

    voltage_inactive = data_df[data_df.columns[2]].dropna()
    y_inactiv = data_df[data_df.columns[3]].dropna()

    return voltage_active, y_activ, voltage_inactive, y_inactiv
    ###