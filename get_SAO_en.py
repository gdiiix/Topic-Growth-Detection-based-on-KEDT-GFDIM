import spacy,re
import pandas as pd

nlp = spacy.load('en_core_web_md')
stopwords = nlp.Defaults.stop_words

with open("stopwords.txt") as inf:
    stopwords_to_append = inf.read().splitlines()
stopwords.update(stopwords_to_append)   #将自定义停用词表中的单词添加到默认的停用词表中

def cleaned_noun_chunk(noun):
    noun_cleaned = re.sub("( comprising$)", "", noun)
    return noun_cleaned


def get_SAO_en(sentence, model=nlp):
    sentence = sentence.replace("said", "the")

    doc = model(sentence)
    res = []

    # get all noun chunks 
    nouns = [n for n in doc.noun_chunks]

    ############################# PART1 #############################
    # filter for dobj
    nouns_dobj = [n for n in nouns if n.root.dep_ in ["dobj", "appos"]]

    for n in nouns_dobj:
        object = " ".join([w.text for w in n if w.pos_!="DET"])
        verb = n.root.head
        if verb.dep_ in ["conj"] and verb.head.pos_ == "VERB":
            verb = verb.head

        subject = None
        # situation 1: acl 
        if verb.dep_ == "acl":
            subject = verb.head
            while subject.dep_ == "acl":
                subject = subject.head

        # situation 2: nsubj
        else:
            subject_node = [child for child in verb.children if child.dep_=="nsubj"]
            if subject_node:
                subject = subject_node[-1]  # suppose the sentence follows the order of subject-verb-object and "-1" refers to the subject which is closer to the dobj
    
            # situation 3: advcl + nsubj
            elif verb.dep_ == "advcl":
                subject_node = [child for child in verb.head.children if child.dep_=="nsubj"]
                if subject_node: 
                    subject = subject_node[-1]

        # find noun chunk that includes the subject noun
        if subject:
            if subject.pos_ == "PRON" and verb.dep_=="relcl":
                subject = verb.head

            try:
                subject = [nn for nn in nouns if subject in nn][0]
                subject = " ".join([w.text for w in subject if w.pos_!="DET"])
            except IndexError:
                subject = subject.text

            objects = [object]

            # check if object has other conjunct objects
            conj_obj = [child for child in n.root.children if child.dep_=="conj"]
            if conj_obj:
                # go deeper (for conj that has another conj)
                conj_obj_deeper = [child for c in conj_obj for child in c.children if child.dep_=="conj"]
                while conj_obj_deeper:
                    conj_obj.extend(conj_obj_deeper)
                    conj_obj_deeper = [child for c in conj_obj_deeper for child in c.children if child.dep_=="conj"]
        
                for obj in conj_obj:
                    try:
                        obj_chunk = [nn for nn in nouns if obj in nn][0]
                        if obj_chunk:
                            objects.append(" ".join([w.text for w in obj_chunk if w.pos_!="DET"]))
                    except IndexError:
                        continue

            for object in objects:
                if (subject not in stopwords and object not in stopwords) and (subject!=object):
                    res.append((cleaned_noun_chunk(subject), verb.lemma_, cleaned_noun_chunk(object)))

    ############################# PART2 #############################
    # for passive form
    passive_verbs = [w for w in doc if w.pos_ == "VERB" and [c for c in w.children if c.dep_ in ["nsubjpass", "agent"]]]

    for verb in passive_verbs:
        subject = [child for child in verb.children if child.dep_ in ["nsubjpass", "agent"]][-1]
        try:
            subject = [nn for nn in nouns if subject in nn][0]
            subject = " ".join([w.text for w in subject if w.pos_!="DET"])
        except (IndexError, AttributeError) as e:
            continue
        
        try:
            prep = [child for child in verb.children if child.dep_ == "prep"][-1]
            pobjs = [child for child in prep.children if child.dep_ == "pobj"]

            pobjs_conj = [child for pobj in pobjs for child in pobj.children if child.dep_=="conj"]
            while pobjs_conj:
                pobjs.extend(pobjs_conj)
                pobjs_conj = [child for pobj in pobjs_conj for child in pobj.children if child.dep_=="conj"]

            for object in pobjs:
                try:
                    object = [nn for nn in nouns if object in nn][0]
                    object = " ".join([w.text for w in object if w.pos_!="DET"])
                except IndexError:
                   continue 

                if (subject not in stopwords and object not in stopwords) and (subject!=object):
                    verb_text = " ".join([w.text for w in doc if (w==verb) or (abs(w.i - verb.i)<=2 and  w.head==verb and w.dep_ in ["auxpass", "prep"])])
                    verb_text = re.sub("(is|are|being)","be", verb_text)
                    res.append((cleaned_noun_chunk(subject), verb_text, cleaned_noun_chunk(object)))
            
        except IndexError:
            continue

    return res


def process_excel_file(file_path):
    df = pd.read_excel(file_path)

    sao_results = []
    original_texts = []
    for column in df.columns:
        for sentence in df[column]:
            if pd.notnull(sentence):
                sao_structure = get_SAO_en(sentence, model=nlp)
                sao_results.extend(sao_structure)
                original_texts.extend([sentence] * len(sao_structure))

    return sao_results, original_texts

def save_sao_results_to_excel(input_file_path, output_file_path):
    sao_results, original_texts = process_excel_file(input_file_path)

    sao_df = pd.DataFrame({"Original Text": original_texts,
                           "Subject": [sao[0] for sao in sao_results],
                           "Verb": [sao[1] for sao in sao_results],
                           "Object": [sao[2] for sao in sao_results]})

    sao_df.to_excel(output_file_path, index=False)

def main():
    input_excel_file = "2022.xlsx"
    output_excel_file = "2022输出.xlsx"
    save_sao_results_to_excel(input_excel_file, output_excel_file)











#def main():
#   sentence = "The invention relates to an autonomous and secure environment in which complex applications can run using a traditional chip card (90), also called a smart card. For this purpose, a method for executing applications in a secure device (20) that can be connected to an external communication device (120) is provided. According to the method, a sealed command to call an application stored in the device (20) is authenticated by a chip card (90) arranged in the device. It is also checked whether the application may be executed by the device (20). Said check occurs inside the device (20, 100) but outside the chip card (90). If the application may be executed by the device (20), the application is executed in the device after successful authentication."
#   sao_structure = get_SAO_en(sentence, model=nlp)

    #for sao in sao_structure:
      #  print(sao)



if __name__ == "__main__":
    main()