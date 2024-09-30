import tkinter as tk
from tkinter.messagebox import showinfo, askquestion, WARNING
from tkinter import filedialog
#import matplotlib.pyplot as plt
#from filters import *
import os

class MainWindow(tk.Tk):
    def __init__(self, main_func):
        super().__init__()

        self.title('sodiuMm')  
        self.geometry('300x400')

        cwd = os.getcwd()
        icon_path = cwd + '/sodiuMm_icon.png'
        ##icon_path = 'C:\\Users\\user\\Dropbox\\Mine\\WorkSpace\\solutions\\calcium_transient\\kai_icon.png'
        ##icon_path = 'C:/custom/src_prog_gui/kai_icon.png'
        self.iconphoto( True, tk.PhotoImage(file=icon_path) )
        self.main_func = main_func

        # Select input file path
        self.labelDummy_61 = tk.Label(self, text='').pack(side='top', ipady=10)
        self.buttonGetInputDataPath = tk.Button(self, text='Select input file path', command=self.getInputDataPath)   
        self.buttonGetInputDataPath.pack(side='top', ipady=10)
        #self.buttonGetInputDataPath.config(state='disabled') # inaccasable before setting global params

        # Select output file path
        self.labelDummy_101 = tk.Label(self, text='').pack(side='top', ipady=10)
        self.buttonGetOutputDataPath = tk.Button(self, text='Select output file path', command=self.getOutputDataPath)   
        self.buttonGetOutputDataPath.pack(side='top', ipady=10)
        self.buttonGetOutputDataPath.config(state='disabled') # inaccasable before choosing input file path 

        # Start main programme
        self.labelDummy_81 = tk.Label(self, text='').pack(side='top', ipady=10)  
        self.buttonStartMain = tk.Button(self, text='Start', width=25, command=self.main_func) #main
        self.buttonStartMain.pack(side='top', ipady=10)
        self.buttonStartMain.config(state='disabled') # inaccasable before choosing output file path

        # Close programme window
        self.labelDummy_121 = tk.Label(self, text='').pack(side='top', ipady=10)
        self.buttonExit = tk.Button(self, text='Exit', width=25, command=self.destroy, fg='darkred')#.grid(row=5, column=1)
        self.buttonExit.pack(side='top', ipady=1)


    # inputExcel
    def getInputDataPath(self):
        filetypes = (('Excel files', '*.xlsx'), ('CSV files', '*.csv'))
        input_file_name = filedialog.askopenfilename(title='Select input data', initialdir='/', filetypes=filetypes)
        if len(input_file_name) == 0: input_file_name = 'Data not selected';
        else: 
            self.buttonGetOutputDataPath.config(state='normal', fg='green')
            self.buttonGetInputDataPath.config(fg='black')
        showinfo(title='Selected data file', message=f'Input data path:\n{input_file_name}')  
        self.InputDataPath = input_file_name
        return self.InputDataPath
    
    def getOutputDataPath(self):
        filetypes = (('Excel files', '*.xlsx'), ('CSV files', '*.csv'))
        output_file_name = filedialog.asksaveasfilename(title='Select output file name', initialdir='/', filetypes=filetypes)
        if len(output_file_name) == 0: output_file_name = 'Output path not selected'
        else: 
            self.buttonStartMain.config(state='normal', fg='green')
            self.buttonGetOutputDataPath.config(fg='black')
            output_file_name += '.xlsx'
        showinfo(title='Output data path', message=f'Output data path:\n{output_file_name}')
        self.OutputDataPath = output_file_name
        return self.OutputDataPath

    def setInputDataPath(self):
        return self.InputDataPath
    
    def setOutputDataPath(self):
        return self.OutputDataPath