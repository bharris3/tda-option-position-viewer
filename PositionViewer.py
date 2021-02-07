from td.client import TDClient  # https://github.com/areed1192/td-ameritrade-python-api
from datetime import datetime
import pandas as pd
import tkinter as tk
import numpy as np
import os


def main():

    #input login details
    TDSession = TDClient(
        client_id=os.environ["TD_CLIENT_ID"],
        redirect_uri=os.environ["TD_REDIRECT_URL"],
        credentials_path=os.environ["TD_CREDENTIALS_PATH"]
    )

    #login
    TDSession.login()

    #return a df of our positions and list of tickers (we'll use the list to know which ticker prices we need to update)
    pos_df, tickers_distinct = get_positions(TDSession)

    options_list, column_titles, final_df = get_prices(TDSession, tickers_distinct, pos_df)

    open_window(column_titles,options_list,TDSession, tickers_distinct, pos_df)

def update_prices(TDSession, tickers_distinct, pos_df, labels_toupdate, master_window):

    options_list, column_titles, final_df = get_prices(TDSession, tickers_distinct, pos_df)

    updatelist = options_list[5:9]

    data = [x for y in updatelist for x in y]

    for i in range(len(labels_toupdate)):
        label = labels_toupdate[i]
        label.config(text=data[i])

    #update prices every 3 seconds. This method runs an infinite loop until you close the window
    master_window.after(3000, update_prices,TDSession, tickers_distinct, pos_df, labels_toupdate, master_window)
    master_window.mainloop()

def get_positions(TDSession):

    api_positions = TDSession.get_accounts(account='all', fields=['positions'])[0]
    # api_positions is returned as a list, so we want to slice it on 0 because we only have 1 account
    # should we open new accounts, this will need to be amended

    pos_list = []

    # our pos_list will only have 6 columns worth of data. We can only make a df off that list with the same # of columns
    column_titles = ["Position", "PutCall", "Ticker", "Quantity", "Strike", "expDate"]

    # slice the api_positions dict on "securitiesAccount" since that is what we trade in. Always static.
    # Then we only want "positions" within the securities account. This will return a list of positions as dicts.
    positions = api_positions["securitiesAccount"]["positions"]

    for pos_dict in positions:

        if pos_dict["shortQuantity"] != 0:
            quantity = pos_dict["shortQuantity"]
            position = "Short"
        else:
            quantity = pos_dict["longQuantity"]
            position = "Long"

        if pos_dict["instrument"]["assetType"].title() == "Option":
            assetType = pos_dict["instrument"]["assetType"].title()
            putCall = pos_dict["instrument"]["putCall"].title()
            ticker = pos_dict["instrument"]["underlyingSymbol"]

            underscore_position = pos_dict["instrument"]["symbol"].index("_")
            exp_date = datetime.strftime(
                datetime.strptime(pos_dict["instrument"]["symbol"][underscore_position + 1:underscore_position + 7], "%m%d%y"),
                "%m/%d/%Y")
            strike = pos_dict["instrument"]["symbol"][underscore_position + 8:]

            pos_list.append([position, putCall, ticker, quantity, strike, exp_date])

    pos_df = pd.DataFrame(pos_list, columns=column_titles)
    pos_df["Strike"] = pos_df["Strike"].astype(float)
    pos_df.sort_values(["expDate", "Ticker", "Strike"], inplace=True, ignore_index=True)

    tickers_distinct = pos_df["Ticker"].unique().tolist()

    return pos_df, tickers_distinct


def get_prices(TDSession, tickers_distinct, pos_df):

    #get the prices for our tickers
    quotes = TDSession.get_quotes(instruments=tickers_distinct)

    column_titles = ['Position', 'PutCall', 'Ticker', 'Quantity', 'Strike', 'Spot', 'InTheMoney', 'DistToATM', 'PctToATM',
                     'expDate']

    final_df = pd.DataFrame(columns=column_titles)

    for ticker in tickers_distinct:
        price = quotes[ticker]["lastPrice"]
        ticker_df = pos_df.copy().loc[pos_df["Ticker"] == ticker]
        ticker_df["Spot"] = price

        # We need a True/False if the option is ITM or OTM
        itm_conditions = [
            (ticker_df["PutCall"] == "Put") & (price < ticker_df["Strike"]),
            (ticker_df["PutCall"] == "Call") & (price > ticker_df["Strike"])
        ]

        itm_values = [True, True]

        #filter the df based on our conditions, and add some columns with calculations we'd like to see in the tkinter window
        ticker_df["InTheMoney"] = np.select(itm_conditions, itm_values)
        ticker_df["InTheMoney"] = np.where(ticker_df["InTheMoney"] == 0, "Out the money", "IN THE MONEY")

        ticker_df["DistToATM"] = np.where((ticker_df["PutCall"] == "Put"), round(price - ticker_df["Strike"], 2),
                                          round(ticker_df["Strike"] - price, 2))
        ticker_df["PctToATM"] = round((ticker_df["DistToATM"] / price) * 100, 2)
        ticker_df = ticker_df.reindex(columns=column_titles)
        final_df = final_df.append(ticker_df)

    options_list = [final_df[col].tolist() for col in final_df]

    return options_list, column_titles, final_df

def open_window(column_titles,options_list,TDSession, tickers_distinct, pos_df):

    master_window = tk.Tk(className=" TD Position Viewer")
    master_window.geometry("600x1100")

    #maker the labelframes, which we will use as columns of tables
    pos_labelframe = tk.LabelFrame(master_window, text="Position")
    putcall_labelframe = tk.LabelFrame(master_window, text="PutCall")
    ticker_labelframe = tk.LabelFrame(master_window, text="Ticker")
    quantity_labelframe = tk.LabelFrame(master_window, text="Quantity")
    strike_labelframe = tk.LabelFrame(master_window, text="Strike")
    spot_labelframe = tk.LabelFrame(master_window, text="Spot")
    itm_labelframe = tk.LabelFrame(master_window, text="InTheMoney")
    distatm_labelframe = tk.LabelFrame(master_window, text="DistToATM")
    pctatm_labelframe = tk.LabelFrame(master_window, text="PctToATM")
    exp_labelframe = tk.LabelFrame(master_window, text="expDate")

    lblframes = [pos_labelframe, putcall_labelframe, ticker_labelframe, quantity_labelframe, strike_labelframe,
                 spot_labelframe, itm_labelframe, distatm_labelframe, pctatm_labelframe, exp_labelframe]

    labels = []

    labelframe_count = 0
    slicer = 0
    labelframe_col = 1

    #fill each labelframe/column with the labels from our lists. The lists are pre-sorted based on how we appended, so the labels will flow through into the proper labelframes
    for frame in lblframes:

        labelframe_count += 1

        frame.grid(row=1, column=labelframe_col)

        for x in options_list[slicer]:

            if (column_titles[slicer] == "PctToATM" and x <= 0) or (column_titles[slicer] == "InTheMoney" and x == "IN THE MONEY"):
                label = tk.Label(frame, text=x, fg="black", bg="red2")
            elif column_titles[slicer] == "PctToATM" and abs(x) <= 1:
                label = tk.Label(frame, text=x, fg="black", bg="dark orange")
            elif column_titles[slicer] == "PctToATM" and abs(x) <= 2:
                label = tk.Label(frame, text=x, fg="black", bg="gold")
            else:
                label = tk.Label(frame, text=x)

            labels.append(label)
            label.pack()

        labelframe_col += 1
        slicer += 1

    labels_toupdate = labels[(lblframes.index(spot_labelframe) * 2):((lblframes.index(pctatm_labelframe) * 2) + 2)]
    #run the price updating loop
    update_prices(TDSession, tickers_distinct, pos_df, labels_toupdate, master_window)

main()