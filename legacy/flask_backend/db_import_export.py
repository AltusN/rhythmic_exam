import csv, sqlite3, os, sys

DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "rhytmic.db")

USAGE = """
The first paramters should be whether to [i]mport or [e]xport the exam questions
The second optional parameter should be where the db is (default is to look for it
next to this script as 'rhytmic.db'). 
"""

def export_all(db:str) -> None:
    #export the entire database to csv files
    sql = "SELECT name FROM sqlite_master WHERE type='table';"
    con = sqlite3.connect(db)
    cur = con.cursor().execute(sql).fetchall()
    
    print(cur)
    
def import_questions(database:str, csv_to_import:str) -> None:

    temp_table = "temp_questions"
    exam_questions_table = "exam_questions"

    print(f"[i] Open connection to [{database}]...", end=" ")
    con = sqlite3.connect(database)
    cur = con.cursor()
    print("done")

    print("[i] Delete the tempory table if it exists...", end=" ")
    cur.execute(f"DROP TABLE IF EXISTS {temp_table}")
    print("done.")

    print("[i] Making backup of current exam questions...", end=" ")
    cur.execute(f"CREATE TABLE {temp_table} AS SELECT * FROM {exam_questions_table}")
    print("done.")
    
    print("[i] Deleting records...", end=" ")
    cur.execute("DELETE FROM exam_questions")
    con.commit()
    print("done.")

    print(f"[i] Reading in csv data from [{csv_to_import}]")
    with open(csv_to_import, 'r', encoding='utf-8') as fin:
        records = csv.DictReader(fin)
        to_db = [(
            i['id'],
            i['question_id'],
            i['question'],
            i['question_type'],
            i['question_images'],
            i['option_a'],
            i['option_b'],
            i['option_c'],
            i['option_d'],
            i['answer'],
            i['question_category'],
            i['exam_level']
        ) for i in records]

    #remove the header record

    INSERT_SQL = '''
    INSERT INTO exam_questions(
        id,
        question_id, 
        question,
        question_type, 
        question_images,
        option_a,
        option_b,
        option_c,
        option_d,
        answer,
        question_category,
        exam_level) VALUES (?,?,?,?,?,?,?,?,?,?,?,?);
    '''

    print(f"[i] Insert {len(to_db)} records into table...", end=" ") 
    try:
        cur.executemany(INSERT_SQL, to_db)
        # if the above succeeds, then we don't need the temp table anymore
        cur.execute(f"DROP TABLE IF EXISTS {temp_table}")
        con.commit()
        print("done")
    except Exception as e:
        print(["[x] Something went wrong with the questions insert. rolling back", e])
        cur.execute(f"DELETE FROM {exam_questions_table}")
        cur.execute(f"INSERT INTO {exam_questions_table} SELECT * from {temp_table}")
        cur.execute(f"DROP TABLE IF EXISTS {temp_table}")
        con.commit()
    finally:
        con.close()

    print("[i] Exit")

def export_questions(database:str, csv_out:str) -> None:

    exam_questions_table = "exam_questions"

    print(f"[i] Open connection to [{database}]...", end=" ")
    con = sqlite3.connect(database)
    cur = con.cursor()
    print("done.")
    
    print(f"[i] Reading records from {exam_questions_table} table...", end=" ")
    rs = cur.execute(f"SELECT * FROM {exam_questions_table}")
    print("done.")

    print("[i] Exporting questions to csv...", end=" ")

    with open(csv_out, 'w', newline='', encoding='utf-8') as f_out:
        csv_writer = csv.writer(f_out,)
        # write out the header
        csv_writer.writerow([i[0] for i in rs.description])
        # and then the data
        csv_writer.writerows(rs)

    print("done.")

    # Don't need the connectionn anymore
    con.close()

if __name__=="__main__":
    
    mode = None
    db = None
    csv_file = None

    # if you know how to read this, you already know this is a shortcut intended
    # for the developer
    if len(sys.argv) == 4:
        # only check the mode.. the rest is up to the user to have correct
        print(f"[i] All parameters specified: {sys.argv[1:]}")
        mode = sys.argv[1]
        db = sys.argv[2]
        csv_file = sys.argv[3]

        match mode:
            case "i":
                import_questions(db, csv_file)
            case "e":
                export_questions(db, csv_file)
            case "ee":
                export_all(db)
            case _:
                print("[x] Could not determine the mode.")
    else:
        print("** Exam question import / export **")
        
        mode = input("[q] (i)mport or (e)xport ('ee' to export everything)? ")
        
        if mode.lower() not in ('i', 'e', 'ee'):
            print(f"[x] Expected 'i', 'e' or 'ee', not {mode}")
            exit()
        else:
            mode = mode.lower()

        # Get the database location
        db = input("[q] Location of database: ")

        if db is None or db == "":
            print(f"[i] No database location specified, using default {DEFAULT_DB_PATH}")
            db = DEFAULT_DB_PATH
        elif not os.path.isfile(db):
            print("[x] Database location is not valid")
            exit()
        # don't need a csv file if we're exporting everything
        if not mode == 'ee':
            csv_file = input("[q] Location of csv: ")
            if csv_file == "" and mode == 'e':
                csv_file = "exported_questions.csv"
                print(f"[i] Defaulting to {csv_file}")
            elif mode == 'i' and not os.path.isfile(csv_file):
                print(f"[x] Invalid file location specided {csv_file}")
                exit()
        
        # Go do the work
        match mode:
            case "e":
                export_questions(db, csv_file)
            case 'i':
                import_questions(db, csv_file)
            case 'ee':
                export_all(db)
            case _:
                print(f"[x] Somehow we got here with mode '{mode}' but should not have.")
                exit()
