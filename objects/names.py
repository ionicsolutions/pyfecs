"""
PyFECS assigns names to timeWindows and channels, which makes it much easier
to use and debug. If the user does not assign names, this module will assign
random names so that we don't end up with tons of 'unnamed' windows nobody can
tell apart.
"""
from random import randint

names = ["Hannah Abbott", "Bathsheda Babbling", "Ludo Bagman",
         "Bathilda Bagshot", "Katie Bell", "Cuthbert Binns",
         "Phineas Nigellus Black", "Regulus Arcturus Black", "Sirius Black",
         "Amelia Bones", "Susan Bones", "Terry Boot", "Lavender Brown",
         "Millicent Bulstrode", "Charity Burbage", "Frank Bryce",
         "Alecto Carrow", "Amycus Carrow", "Reginald Cattermole",
         "Mary Cattermole", "Cho Chang", "Penelope Clearwater",
         "Michael Corner", "Vincent Crabbe, Sr.", "Vincent Crabbe",
         "Colin Creevey", "Dennis Creevey", "Dirk Cresswell",
         "Bartemius Crouch, Sr.", "Bartemius Crouch, Jr.",
         "John Dawlish", "Fleur Delacour", "Gabrielle Delacour",
         "Dedalus Diggle", "Amos Diggory", "Cedric Diggory", "Elphias Doge",
         "Antonin Dolohov", "Aberforth Dumbledore", "Albus Dumbledore",
         "Ariana Dumbledore", "Dudley Dursley", "Marjorie Dursley",
         "Petunia Dursley", "Vernon Dursley", "Marietta Edgecombe",
         "Everard", "Arabella Figg", "Argus Filch", "Justin Finch-Fletchley",
         "Seamus Finnigan", "Marcus Flint", "Nicolas Flamel",
         "Mundungus Fletcher", "Filius Flitwick", "Florean Fortescue",
         "Cornelius Fudge", "Marvolo Gaunt", "Merope Gaunt", "Morfin Gaunt",
         "Anthony Goldstein", "Goyle Sr", "Gregory Goyle", "Hermione Granger",
         "Gregorovitch", "Fenrir Greyback", "Gellert Grindelwald",
         "Wilhelmina Grubbly-Plank", "Godric Gryffindor", "Rubeus Hagrid",
         "Rolanda Hooch", "Mafalda Hopkirk", "Helga Hufflepuff",
         "Angelina Johnson", "Lee Jordan", "Bertha Jorkins",
         "Igor Karkaroff", "Viktor Krum", "Bellatrix Lestrange",
         "Rabastan Lestrange", "Rodolphus Lestrange", "Gilderoy Lockhart",
         "Alice Longbottom", "Augusta Longbottom", "Frank Longbottom",
         "Neville Longbottom", "Luna Lovegood", "Xenophilius Lovegood",
         "Remus Lupin", "Walden Macnair", "Draco Malfoy", "Lucius Malfoy",
         "Narcissa Malfoy", "Madam Malkin", "Olympe Maxime", "Ernie Macmillan",
         "Minerva McGonagall", "Alastor Moody", "Theodore Nott",
         "Garrick Ollivander", "Pansy Parkinson", "Padma Patil",
         "Parvati Patil", "Peter Pettigrew", "Antioch Peverell",
         "Cadmus Peverell", "Ignotus Peverell", "Irma Pince",
         "Sturgis Podmore", "Poppy Pomfrey", "Harry Potter", "James Potter",
         "Lily Potter", "Ernest Prang", "Quirinus Quirrell", "Helena Ravenclaw",
         "Rowena Ravenclaw", "Mary Riddle", "Thomas Riddle", "Tom Riddle Sr",
         "Tom Marvolo Riddle", "Demelza Robins", "Augustus Rookwood",
         "Albert Runcorn", "Scabior", "Newt Scamander", "Rufus Scrimgeour",
         "Kingsley Shacklebolt", "Stan Shunpike", "Aurora Sinistra",
         "Rita Skeeter", "Horace Slughorn", "Salazar Slytherin",
         "Hepzibah Smith", "Zacharias Smith", "Severus Snape", "Alicia Spinnet",
         "Pomona Sprout", "Pius Thicknesse", "Dean Thomas", "Andromeda Tonks",
         "Nymphadora Tonks", "Ted Tonks", "Travers",
         "Sybill Patricia Trelawney", "Dolores Jane Umbridge",
         "Emmeline Vance", "Romilda Vane", "Septima Vector", "Lord Voldemort",
         "Myrtle Warren", "Arthur Weasley", "Bill Weasley", "Charlie Weasley",
         "Fred Weasley", "George Weasley", "Ginny Weasley", "Molly Weasley",
         "Percy Weasley", "Ron Weasley", "Oliver Wood", "Kennilworthy Whisp",
         "Yaxley", "Blaise Zabini", "Aragog", "Bane", "Beedle the Bard",
         "The Bloody Baron", "Buckbeak", "Sir Cadogan", "Crookshanks",
         "Dobby", "Enid", "Errol", "Fang", "The Fat Friar", "Fridwulfa",
         "The Fat Lady", "Fawkes", "Firenze", "Fluffy", "Grawp", "Griphook",
         "Hedwig", "Hokey", "Kreacher", "Magorian", "Mrs Norris",
         "Great Aunt Muriel", "Nagini", "Nearly Headless Nick",
         "Norbert", "Peeves", "Pigwidgeon", "Madam Rosmerta", "Ronan",
         "Scabbers", "Trevor", "Winky"]

moreNames = []

def getName():
    """Return a placeholder name."""
    global names  # see below
    global moreNames
    if len(names) < 1:
        for name in moreNames:
            names.append(name)
            moreNames.remove(name)
        #raise Exception("VeryBadStudentError", "We have more than 170 dummy "
        #                "names we assign to your unnamed time windows and "
        #                "channels. It's not that hard to assign meaningful "
        #                "names, is it? (On the other hand, I'm impressed by "
        #                "the complexity of your sequence.)")
    name = names[randint(0, len(names) - 1)]
    # while we cannot ensure that names are not given out twice globally, we can
    # at least ensure that each import of FECSNames returns unique names
    names.remove(name)
    moreNames.append(name)
    return name

if __name__ == "__main__":
    print("Accio Names!")
    for i in range(10):
        print(getName(), len(names))
