from datetime import datetime, timedelta

import gspread
from gspread.utils import Dimension

sa = gspread.service_account(filename="%APPDATA%/gspread/service_account.jso")
sh = sa.open("Trainingsprotokoll Lukas Mehl")

class SheetsClient:
    def get_first_not_completed_day(self):
        latestWeekWorksheet = sh.worksheets()[2]
        weekAndTimeframe = latestWeekWorksheet.acell("B1").value.split()
        weekStartDate = datetime.strptime(weekAndTimeframe[3], '%d.%m.%Y')

        data_range = latestWeekWorksheet.get(range_name='B3:O8', major_dimension=Dimension.cols)

        return weekStartDate + timedelta(days=len(data_range)/2)

def main():
    client = SheetsClient()

    print(client.get_first_not_completed_day())

if __name__ == "__main__":
    main()