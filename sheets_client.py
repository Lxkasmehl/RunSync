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

    def set_new_Entry(self, type, date_str, text):
        date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        # Get the week number of the given date
        week_number = date.isocalendar()[1]

        # Check if a worksheet for this week already exists
        worksheet_title = f"KW{week_number}{date.strftime('%y')}"
        worksheets = sh.worksheets()
        existing_worksheet = next((ws for ws in worksheets if ws.title == worksheet_title), None)

        if existing_worksheet is None:
            # If not, duplicate the template worksheet
            template_worksheet = sh.worksheet("leer")
            new_worksheet = sh.duplicate_sheet(source_sheet_id=template_worksheet.id, insert_sheet_index=2,
                                               new_sheet_name=worksheet_title)
            new_worksheet.update_acell("B1:O1",
                                       f"KW {week_number}{date.strftime('%y')} - {date - timedelta(days=date.weekday()):%d.%m.%Y} - {date + timedelta(days=6 - date.weekday()):%d.%m.%Y}")
        else:
            new_worksheet = existing_worksheet

        # Find the column range based on the day of the week
        day_of_week = date.weekday()
        column_offset = day_of_week * 2
        column_range = chr(ord('B') + column_offset) + ":" + chr(ord('B') + column_offset + 1)

        # Find the row range based on the time of day
        if date.hour < 12:
            row_range = "3:5"
        else:
            row_range = "6:8"

        # Find the cell to update based on the type
        if type == "description":
            cell = column_range[0] + str(int(row_range.split(":")[0]) + 1)
        elif type == "private_note":
            cell = column_range[0] + row_range.split(":")[1]
        elif type == "distance":
            cell = column_range[2] + str(int(row_range.split(":")[0]) + 1)
        else:
            raise ValueError("Ungültiger Typ")

        existing_value = new_worksheet.acell(cell).value
        if existing_value:
            new_worksheet.update_acell(cell, f"{existing_value}\n{text}")
        else:
            new_worksheet.update_acell(cell, text)


def main():
    client = SheetsClient()

    client.set_new_Entry(type="description", date_str="2024-06-27T15:00:00Z", text="Number2")
    #print(client.get_first_not_completed_day())

if __name__ == "__main__":
    main()