import wx
import wx.grid as gridlib
import threading
import time
import csv
from EcoOpen.core import FindPapers, DownloadPapers
import pandas as pd

class MyFrame(wx.Frame):
    def __init__(self, *args, **kw):
        super(MyFrame, self).__init__(*args, **kw)
        panel = wx.Panel(self)

        # Create a vertical box sizer
        vbox = wx.BoxSizer(wx.VERTICAL)

        # Create a horizontal box sizer for radio buttons and load DOI button
        hbox_radio_buttons = wx.BoxSizer(wx.HORIZONTAL)

        # Radio buttons for selecting input type
        self.radio_box = wx.RadioBox(panel, label="Select Input Type", choices=["Query", "Author", "DOI"], majorDimension=1, style=wx.RA_SPECIFY_ROWS)
        self.radio_box.Bind(wx.EVT_RADIOBOX, self.on_radio_box_change)
        hbox_radio_buttons.Add(self.radio_box, flag=wx.EXPAND | wx.ALL, border=10)

        # Load DOI button
        self.load_doi_button = wx.Button(panel, label='Load DOI List')
        self.load_doi_button.Bind(wx.EVT_BUTTON, self.on_load_doi_list)
        self.load_doi_button.Disable()  # Initially disable the button
        hbox_radio_buttons.Add(self.load_doi_button, flag=wx.EXPAND | wx.ALL, border=10)

        # Add the horizontal box sizer to the vertical box sizer
        vbox.Add(hbox_radio_buttons, flag=wx.EXPAND | wx.ALL, border=10)

        # Single text input field
        self.input_text = wx.TextCtrl(panel)
        vbox.Add(self.input_text, flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, border=10)

        # Progress bar
        self.progress_bar = wx.Gauge(panel, range=100)
        vbox.Add(self.progress_bar, flag=wx.EXPAND | wx.ALL, border=10)

        # Create a horizontal box sizer for buttons
        hbox_buttons = wx.BoxSizer(wx.HORIZONTAL)

        # Button to find scientific articles
        self.find_button = wx.Button(panel, label='Find Scientific Articles')
        self.find_button.Bind(wx.EVT_BUTTON, self.on_find_articles)
        hbox_buttons.Add(self.find_button, flag=wx.EXPAND | wx.ALL, border=10)

        # Add the horizontal box sizer to the vertical box sizer
        vbox.Add(hbox_buttons, flag=wx.ALIGN_CENTER | wx.ALL, border=10)

        # Grid for spreadsheet-like table
        self.grid = gridlib.Grid(panel)
        self.grid.CreateGrid(5, 5)  # 5 rows and 5 columns
        self.grid.Bind(gridlib.EVT_GRID_CELL_LEFT_CLICK, self.on_cell_click)
        vbox.Add(self.grid, proportion=1, flag=wx.EXPAND | wx.ALL, border=10)

        # Create a horizontal box sizer for the new buttons
        hbox_new_buttons = wx.BoxSizer(wx.HORIZONTAL)

        # Button to remove selected row
        self.remove_row_button = wx.Button(panel, label='Remove Selected Row')
        self.remove_row_button.Bind(wx.EVT_BUTTON, self.on_remove_row)
        hbox_new_buttons.Add(self.remove_row_button, flag=wx.EXPAND | wx.ALL, border=10)

        # Button to save table as .csv
        self.save_csv_button = wx.Button(panel, label='Save Table as .CSV')
        self.save_csv_button.Bind(wx.EVT_BUTTON, self.on_save_csv)
        hbox_new_buttons.Add(self.save_csv_button, flag=wx.EXPAND | wx.ALL, border=10)

        # Checkbox for third party sources
        self.third_party_checkbox = wx.CheckBox(panel, label='Third Party Sources')
        hbox_new_buttons.Add(self.third_party_checkbox, flag=wx.EXPAND | wx.ALL, border=10)

        # Button to download scientific articles
        self.download_button = wx.Button(panel, label='Download Scientific Articles')
        self.download_button.Bind(wx.EVT_BUTTON, self.on_download_articles)
        hbox_new_buttons.Add(self.download_button, flag=wx.EXPAND | wx.ALL, border=10)

        # Add the new horizontal box sizer to the vertical box sizer
        vbox.Add(hbox_new_buttons, flag=wx.ALIGN_RIGHT | wx.ALL, border=10)
        # Add the new horizontal box sizer to the vertical box sizer
        vbox.Add(hbox_new_buttons, flag=wx.ALIGN_RIGHT | wx.ALL, border=10)

        panel.SetSizer(vbox)
        self.status_bar = self.CreateStatusBar()
        self.status_bar.SetStatusText("Ready")
        
        self.SetSize((800, 600))  # Set the window size to 800x600 pixels
        
        
        self.papers = None
        self.Show()

    def on_radio_box_change(self, event):
        if self.radio_box.GetStringSelection() == "DOI":
            self.load_doi_button.Enable()
        else:
            self.load_doi_button.Disable()

    def on_find_articles(self, event):
        input_type = self.radio_box.GetStringSelection()
        input_value = self.input_text.GetValue()
        self.progress_bar.SetValue(0)
        self.thread = threading.Thread(target=self.find_papers_thread, args=(input_type, input_value))
        self.thread.start()

    def find_papers_thread(self, input_type, input_value):
        def progress_callback(current, total):
            progress = int((current / total) * 100)
            wx.CallAfter(self.progress_bar.SetValue, progress)

        if input_type.lower() == 'doi':
            dois = input_value.split(', ')
            papers = FindPapers(doi=dois, callback=progress_callback)
        elif input_type.lower() == "query":
            papers = FindPapers(input_value, callback=progress_callback)
        elif input_type.lower() == "author":
            papers = FindPapers(author=input_value, callback=progress_callback)

        wx.CallAfter(self.update_grid, papers)
        wx.CallAfter(wx.MessageBox, f'Found {len(papers)} papers', 'Info', wx.OK | wx.ICON_INFORMATION)

    def update_grid(self, papers):
        self.papers = papers
        if isinstance(papers, pd.DataFrame):
            self.grid.ClearGrid()
            if self.grid.GetNumberRows() > 0:
                self.grid.DeleteRows(0, self.grid.GetNumberRows())
            if self.grid.GetNumberCols() > 0:
                self.grid.DeleteCols(0, self.grid.GetNumberCols())

            self.grid.AppendCols(len(papers.columns))
            self.grid.AppendRows(len(papers))

            for col, column_name in enumerate(papers.columns):
                self.grid.SetColLabelValue(col, column_name)
                for row in range(len(papers)):
                    self.grid.SetCellValue(row, col, str(papers.iloc[row, col]))

            # Auto resize columns to fit content but limit to a maximum width of 250 pixels
            self.grid.AutoSizeColumns()
            for col in range(self.grid.GetNumberCols()):
                if self.grid.GetColSize(col) > 250:
                    self.grid.SetColSize(col, 250)

    def on_download_articles(self, event):
        with wx.DirDialog(self, "Select output folder", style=wx.DD_DEFAULT_STYLE) as dirDialog:
            if dirDialog.ShowModal() == wx.ID_CANCEL:
                return

            output_folder = dirDialog.GetPath()

            # Start the download process in a new thread
            threading.Thread(target=self.start_download, args=(output_folder,)).start()

    def start_download(self, output_folder):
        def progress_callback(current, total):
            progress = int((current / total) * 100)
            wx.CallAfter(self.progress_bar.SetValue, progress)

        downloaded = DownloadPapers(self.papers, output_folder, callback=progress_callback)
        downloaded.to_csv(f"{output_folder}/downloaded.csv", index=False)
        wx.MessageBox('Download ended! Check the output folder!', 'Info', wx.OK | wx.ICON_INFORMATION)

    def on_load_doi_list(self, event):
        with wx.FileDialog(self, "Open DOI file", wildcard="Text files (*.txt)|*.txt",
                           style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return

            pathname = fileDialog.GetPath()
            try:
                with open(pathname, 'r') as file:
                    dois = file.read().splitlines()
                    self.input_text.SetValue(", ".join(dois))
            except IOError:
                wx.LogError("Cannot open file '%s'." % pathname)

    def on_cell_click(self, event):
        row = event.GetRow()
        self.grid.SelectRow(row)    
        event.Skip()

    def on_remove_row(self, event):
        selected_rows = self.grid.GetSelectedRows()
        if selected_rows:
            for row in reversed(selected_rows):
                self.grid.DeleteRows(pos=row, numRows=1)
                if self.papers is not None:
                    self.papers = self.papers.drop(self.papers.index[row]).reset_index(drop=True)
        else:
            wx.MessageBox('No row selected', 'Info', wx.OK | wx.ICON_INFORMATION)

    def on_save_csv(self, event):
        with wx.FileDialog(self, "Save CSV file", wildcard="CSV files (*.csv)|*.csv",
                           style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as fileDialog:
            if fileDialog.ShowModal() == wx.ID_CANCEL:
                return

            pathname = fileDialog.GetPath()
            try:
                with open(pathname, 'w', newline='') as file:
                    writer = csv.writer(file)
                    for row in range(self.grid.GetNumberRows()):
                        row_data = [self.grid.GetCellValue(row, col) for col in range(self.grid.GetNumberCols())]
                        writer.writerow(row_data)
            except IOError:
                wx.LogError("Cannot save current data in file '%s'." % pathname)

class MyApp(wx.App):
    def OnInit(self):
        frame = MyFrame(None, title="EcoOpen-GUI")
        frame.Show()
        return True

if __name__ == '__main__':
    app = MyApp()
    app.MainLoop()