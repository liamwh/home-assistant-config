#!/usr/bin/env python3

#                           _                  _        _     _
#        _ __ ___  __ _  __| |_ __ ___   ___  | |_ __ _| |__ | | ___  ___
#       | '__/ _ \/ _` |/ _` | '_ ` _ \ / _ \ | __/ _` | '_ \| |/ _ \/ __|
#       | | |  __/ (_| | (_| | | | | | |  __/ | || (_| | |_) | |  __/\__ \
#   ____|_|  \___|\__,_|\__,_|_| |_| |_|\___|  \__\__,_|_.__/|_|\___||___/
#  |_____|
#
# - from github.com/basnijholt/home-assistant-config

# This script generates the HTML table in my README.md.
# It is used in `update-readme.py`.

from jinja2 import Template

tables = {
    "Switches 🎚": [
        ["Philips Hue Dimmer switch", 3, 50.07],
    ],
    "Sensors 🌡": [
        ["Xiaomi Aqara Door Sensor", 2, 16.98],
        ["Philips Hue Motion, Temperature & Humidity Sensor", 1, 39.95],
    ],
    "Vacuum 🧹": [["Xiaomi Mi Roborock S5 Max", 1, 383.92]],
    "Media player 📺🔈": [
        ["Philips The One 58", 1, "nan"],
        ["Google Home Hub", 2, 119.98],
    ],
    "Lights 💡": [  # TODO: Prices not correct
        ["Philips Hue E27 White and Color", 5, 217.88],
        ["Philips Hue E14 White and Color", 3, 131.98],
        ["Philips Hue GU10 White Ambience ", 3, 63],
        ["Philips Hue GU10 White and Color", 3, 119.25],
    ],
    "Hubs 🌎": [["ConBee II", 1, 39.95]],
    "Device tracker 🔍": [
        ["iPhone XS with the iOS app", 1, "nan"],
    ],
}


def add_unit_price(lst):
    return [
        (
            name,
            units,
            round(tot_price / units, 2) if isinstance(tot_price, float) else "nan",
            tot_price,
        )
        for name, units, tot_price in lst
    ]


tables = {title: add_unit_price(lst) for title, lst in tables.items()}
total_per_title = {
    title: sum(x[-1] for x in lst if isinstance(x[-1], float))
    for title, lst in tables.items()
}

table_template = """
<table>
    {%- for k, v in dicts.items() %}
    <thead>
        <tr>
            <th>{{ k }}</th>
            <th>Units (#)</th>
            <th>Price per unit (€)</th>
            <th>Price (€)</th>
        </tr>
    </thead>
    <tbody>
    {%- for name, units, unit_price, tot_price in v %}
        <tr>
            <td>{{ name }}</td>
            <td>{{ units }}</td>
            <td>{{ unit_price }}</td>
            <td>{{ tot_price }}</td>
        </tr>
    {%- endfor %}
        {%- if total_per_title[k] > 0 %}
        <tr>
            <td><i><b>Total</b></i></td>
            <td>&nbsp;</td>
            <td>&nbsp;</td>
            <td>{{ total_per_title[k] | round(2) }}</td>
        </tr>
        {%- endif %}
        <tr>
            <td>&nbsp;</td>
            <td>&nbsp;</td>
            <td>&nbsp;</td>
            <td>&nbsp;</td>
        </tr>
    </tbody>
    {%- endfor %}
    <thead>
        <tr>
            <th>Total</th>
            <th></th>
            <th></th>
            <th>€{{ total }}</th>
        </tr>
    </thead>
</table>"""


template = Template(table_template)
total_cost = sum(
    cost for lst in tables.values() for _, _, _, cost in lst if isinstance(cost, float)
)
html_table = template.render(
    dicts=tables, total=total_cost, total_per_title=total_per_title
)

if __name__ == "__main__":
    print(html_table)
