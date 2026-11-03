# Reads the data of the festival and prints its name.
# Run it from this folder: uv run main.py
#
# The three lines below open the file and turn its JSON text into Python
# dicts and lists. How they work is explained in step 05; for now, use them.

import json
count= {}
long=0
with open("data/festival.json", encoding="utf-8") as file:
    festival = json.load(file)
total = 0
print(festival["name"])
print (f"From {festival["first_day"]} to {festival["last_day"]} ")
print (f"{len(festival["venues"])} venues,{len(festival["artists"])} artists,{len(festival["performances"])} performances")
print("venue :")
for items in festival["venues"]:
     print(f"{items["name"]} : {items["capacity"]} seat ({items["address"]})")
     
     total= total + (items["capacity"])
print (total)

for type in festival["performances"]:
     type = type["kind"]
     count[type] = count.get(type, 0)+1

for kind, number in count.items():   
     print(kind,number)

print ("Le Kiosque :")
for item2 in festival["performances"]:
   
    print (f"{item2["start"]} {item2["title"]}")
    if item2["duration_minutes"]>long:
         long = item2["duration_minutes"]
print (item2["title"], long)

for type2 in festival["performances"]:
     if type2["kind"] == "workshop":
          
          print (f"{type2["title"]} on {type2["start"]} ")

          place= type2["max_participants"]-(len(type2["participants"]))
          print (place)

#jour = str (input("entrez une journee : "))
#start =[]
#for item3 in festival["performances"]:
     #start=item3["start"]
     #start= start.split("T")
     #if start[0]== jour:
          #print (item3["title"],item3["venue"])
     #else:

     

start2= []          #print ("none")
while True:
      jour2= str(input("entrez une date"))
      for item3 in festival["performances"]:
          start2=item3["start"]
          start2= start2.split("T")
          if start2!=jour2:
          if start[0]== jour:
               print("go")