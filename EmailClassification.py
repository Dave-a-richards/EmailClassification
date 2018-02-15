######################
# STANDARD LIBRARIES #
######################
import re

#######################
# 3RD PARTY LIBRARIES #
#######################
from exchangelib import DELEGATE, IMPERSONATION, Account, Credentials, ServiceAccount, \
    EWSDateTime, EWSTimeZone, Configuration, NTLM, CalendarItem, Message, \
    Mailbox, Attendee, Q, ExtendedProperty, FileAttachment, ItemAttachment, \
    HTMLBody, Build, Version
from exchangelib.protocol import BaseProtocol, NoVerifyHTTPAdapter
#this is used to connect to the Watson NLC Service
from watson_developer_cloud import NaturalLanguageClassifierV1

####################
# CUSTOM LIBRARIES #
####################
#this imports all config from config.yaml
from config import settings
#this imports all email_categories from config.yaml
from categories import email_categories


#This line fixes HTTPS SSL Cert Issues
BaseProtocol.HTTP_ADAPTER_CLS = NoVerifyHTTPAdapter



######################################
# GLOBAL VARIABLES                   #
# All values pulled from config.yaml #
######################################
WATSON_USERNAME = settings['watson']['username']
WATSON_PASSWORD = settings['watson']['password']
EMAIL_USERNAME = settings['exchange']['username']
EMAIL_PASSWORD = settings['exchange']['password']
EMAIL_SERVER = settings['exchange']['server']
EMAIL_SMTP = settings['exchange']['smtp']
TRAINING_FILE_MODEL1 = settings['models']['training']['model1_file']
TRAINING_FILE_MODEL2 = settings['models']['training']['model2_file']
TRAINING_FILE_MODEL_D1 = settings['models']['training']['modeld1_file']
TRAINING_FILE_MODEL_D2 = settings['models']['training']['modeld2_file']
TRAINING_FILE_MODEL_S1 = settings['models']['training']['models1_file']
TRAINING_FILE_MODEL_S2 = settings['models']['training']['models2_file']
TRAINING_FILE_CATEGORIES = settings['models']['training']['category_file']
TRAINING_FOLDER = settings['models']['training']['training_folder']
TRAINING_SUBFOLDER1 = settings['models']['training']['training_subfolder_1']
TRAINING_SUBFOLDER2 = settings['models']['training']['training_subfolder_2']
RESULT_ANALYSIS_FILE = settings['models']['analysis']['output_file']
CLASSIFIER_ID_MODEL1 = settings['watson']['classifier_ids']['model1']
CLASSIFIER_ID_MODEL2 = settings['watson']['classifier_ids']['model2']
CLASSIFIER_ID_MODELS1 = settings['watson']['classifier_ids']['models1']
CLASSIFIER_ID_MODELS2 = settings['watson']['classifier_ids']['models2']
CLASSIFIER_ID_MODELD1 = settings['watson']['classifier_ids']['modeld1']
CLASSIFIER_ID_MODELD2 = settings['watson']['classifier_ids']['modeld2']
CLASSIFIER_ID_CATEGORIZE = settings['watson']['classifier_ids']['model_categorize']
REQUIRED_CONFIDENCE = settings['watson']['confidence_requirements']['overall']
REQUIRED_CONFIDENCE_MODEL1 = settings['watson']['confidence_requirements']['model1']
REQUIRED_CONFIDENCE_MODEL2 = settings['watson']['confidence_requirements']['model2']
DISCLAIMERS = settings['disclaimers']
EMAIL_GROUPS = settings['exchange']['email_groups']

#PLACED HERE OUT OF LAZYNESS - FIX LATER
# def generate critical dictionary
def createCriticalDict(category_config):
    temp_dict = {}
    for category in category_config:
        for property in category_config[category]:
            value = category_config[category][property]
            if property =='critical':
                temp_dict[category] = value
    return temp_dict

#This dict holds the email classification as the key and if it is critical as the value loaded from categories.yaml
CRITICAL_DICT = createCriticalDict(email_categories)





##############
# MY METHODS #
##############

#This creates an object that is connected to the email server
def getEmailObject(email_username,email_password,email_server,email_smtp):
    credentials = ServiceAccount(username=email_username, password=email_password)
    config = Configuration(server=email_server, credentials=credentials)
    account = Account(primary_smtp_address=email_smtp, config=config, autodiscover=False, access_type=DELEGATE)
    return account

#This removes line breaks, commas, and disclaimers set in config from the email body
def formatMailBody(mail_body):
    formatted_mail_body = mail_body.replace('\n', ' ').replace('\r', '').replace(',', '')
    for disclaimer in DISCLAIMERS:
        formatted_mail_body = formatted_mail_body.replace(DISCLAIMERS[disclaimer], '')
    return formatted_mail_body

#This identifies which email group the email falls into to preprocess with the correct logic
def identify_email_group(email):
    efrom = email.author.email_address
    email_group = 'unknown'
    for group in EMAIL_GROUPS:
        for address in EMAIL_GROUPS[group]:
            if (EMAIL_GROUPS[group][address]) == efrom.lower():
                email_group = group
    return email_group


#This does the preprocessing of Group1 emails
def preprocessGroup1(emailbody):
    #Find the Document Number
    matched_lines = [line for line in emailbody.split('\n') if 'Document Number:' in line]
    if matched_lines:
        document_number = matched_lines[0].replace('\n', ' ').replace('\r', '').replace(',', '').replace('Document Number:        ', '')
        document_number = 'Document Number: ' + document_number
    else:
        document_number = 'Document Number: '

    #Find the Filer(s)
    matched_lines = [line for line in emailbody.split('\n') if 'Filer:' in line]
    if matched_lines:
        filer = matched_lines[0].replace('\n', ' ').replace('\r', '').replace(',', '').replace('Filer:', '')
        filer = 'Filer: ' + filer
    else:
        filer = 'Filer: '

    # Find the name at the end of the docket text
    start_pos = emailbody.find('Docket Text:')
    end_pos = emailbody.find('Notice has been electronically mailed to:')
    matched_lines = emailbody[start_pos:end_pos]
    start_pos = matched_lines.rfind('(')
    end_pos = matched_lines.rfind(')')
    docket_text_name = matched_lines[start_pos + 1:end_pos]

    # Find the docket text
    start_pos = emailbody.find('Docket Text:')
    temp = '(' + docket_text_name + ')'
    end_pos = emailbody.find(temp)
    docket_text =  emailbody[start_pos:end_pos].replace('\n', ' ').replace('\r', '')

    #Find the names and emails it was mailed to
    start_pos = emailbody.find('Notice has been electronically mailed to:')
    end_pos = emailbody.find('Notice will not be electronically mailed to:')
    matched_lines = emailbody[start_pos:end_pos]
    matched_lines = matched_lines.replace('\n', ' ').replace('\r', '').replace('Notice has been electronically mailed to:', '')
    word_list = matched_lines.split()
    try:
        notice_mailed_to = matched_lines.replace(word_list[-1],'')
    except:
        notice_mailed_to = ' '

    #Combines into a single string
    preprocessed_text = document_number + ' ' + filer + ' ' + ' Docket Text Name: ' + docket_text_name +' Notice Mailed To: ' + notice_mailed_to + docket_text
    preprocessed_text = re.sub(r'\w+:\/{2}[\d\w-]+(\.[\d\w-]+)*(?:(?:\/[^\s/]*))*', '', preprocessed_text)
    preprocessed_text = preprocessed_text.replace('<', '').replace('  ',' ').replace('   ',' ').replace('    ',' ').replace(',', '')
    return preprocessed_text

#This does the preprocessing of Group2 emails
def preprocessGroup2(emailbody):
    preprocessed_text = emailbody
    #Find the Document Number
    matched_lines = ''
    iterator = iter(preprocessed_text.splitlines())
    for line in iterator:
        if 'Doc #' in line:
            matched_lines = next(iterator)
    if matched_lines != '':
        document_number = matched_lines.split(' ', 1)[0]
    else:
        document_number = 'No document attached'
    # Find the Filer(s)
    matched_lines = [line for line in emailbody.split('\n') if 'User Name:' in line]
    if matched_lines:
        filer = matched_lines[0].replace('\n', ' ').replace('\r', '').replace(',', '').replace('User Name:   ', 'Filer: ')
    else:
        filer = 'Filer: '
    # Find the Filer(s) email
    matched_lines = [line for line in emailbody.split('\n') if 'Email Service Address:' in line]
    if matched_lines:
        filer_email = matched_lines[0].replace('\n', ' ').replace('\r', '').replace(',', '').replace('Email Service Address:',
                                                                                               'Filer Email: ')
    else:
        filer_email = 'Filer Email: '
    # Find the Document Type
    #print(preprocessed_text)
    iterator = iter(preprocessed_text.splitlines())
    document_type = 'Unknown'
    for line in iterator:
        if 'Document Type' in line:
            matched_lines = next(iterator)
            #print('doc type')
            try:
                document_type = matched_lines.split(' ', 1)[1].replace(' ','')
                document_type = document_type[:document_type.find('<')]
            except:
                document_type = ''
            #print(document_type)

    output_text = 'Document Number: ' + document_number + ' ' + filer + ' Document Type: ' + document_type + ' ' + filer_email
    output_text = output_text.replace(',', '')
    return output_text

#gets Actionable/Non-Actionable classification from Watson using model 1
#model 1 is the first 1000 characters of the email body after removing any standard disclaimers
def getClassificationModel1(email):
    tempString = formatMailBody(email.text_body)
    outputString = tempString[:1000]
    #print(outputString)
    natural_language_classifier = NaturalLanguageClassifierV1(
        username=WATSON_USERNAME,
        password=WATSON_PASSWORD)
    classification = natural_language_classifier.classify(CLASSIFIER_ID_MODEL1, outputString)
    top_classification = classification['top_class']
    temp_classes = classification['classes']
    for i in temp_classes:
        if i['class_name'] == top_classification:
            top_classification_confidence = i['confidence']
    classification_output = [top_classification, top_classification_confidence]
    return classification_output

#gets Actionable/Non-Actionable classification from Watson using model 2
#model 2 is a classification of the pre-processed email body
def getClassificationModel2(email):
    preprocessing_group = identify_email_group(email)
    if preprocessing_group == 'email_group_1':
        tempString = preprocessGroup1(email.text_body)
        outputString = tempString[:1000]
        #print(outputString)
        natural_language_classifier = NaturalLanguageClassifierV1(
            username=WATSON_USERNAME,
            password=WATSON_PASSWORD)
        classification = natural_language_classifier.classify(CLASSIFIER_ID_MODEL2, outputString)
        top_classification = classification['top_class']
        temp_classes = classification['classes']
        for i in temp_classes:
            if i['class_name'] == top_classification:
                top_classification_confidence = i['confidence']
        classification_output = [top_classification, top_classification_confidence]
    elif preprocessing_group == 'email_group_2':
        tempString = preprocessGroup2(email.text_body)
        outputString = tempString[:1000]
        #print(outputString)
        natural_language_classifier = NaturalLanguageClassifierV1(
            username=WATSON_USERNAME,
            password=WATSON_PASSWORD)
        classification = natural_language_classifier.classify(CLASSIFIER_ID_MODEL2, outputString)
        top_classification = classification['top_class']
        temp_classes = classification['classes']
        for i in temp_classes:
            if i['class_name'] == top_classification:
                top_classification_confidence = i['confidence']
        classification_output = [top_classification, top_classification_confidence]
    else:
        classification_output = ['not recognized', 0.00]
    return classification_output

#gets Actionable/Non-Actionable classification from Watson using model 1
#model S1 is the first 1000 characters of the email body after removing any standard disclaimers
#this model is for the supreme court emails
def getClassificationModelS1(email):
    tempString = formatMailBody(email.text_body)
    outputString = tempString[:1000]
    #print(outputString)
    natural_language_classifier = NaturalLanguageClassifierV1(
        username=WATSON_USERNAME,
        password=WATSON_PASSWORD)
    classification = natural_language_classifier.classify(CLASSIFIER_ID_MODELS1, outputString)
    top_classification = classification['top_class']
    temp_classes = classification['classes']
    for i in temp_classes:
        if i['class_name'] == top_classification:
            top_classification_confidence = i['confidence']
    classification_output = [top_classification, top_classification_confidence]
    return classification_output

#gets Actionable/Non-Actionable classification from Watson using model 1
#model S1 is the first 1000 characters of the email body after removing any standard disclaimers
#this model is for the district court emails
def getClassificationModelD1(email):
    tempString = formatMailBody(email.text_body)
    outputString = tempString[:1000]
    #print(outputString)
    natural_language_classifier = NaturalLanguageClassifierV1(
        username=WATSON_USERNAME,
        password=WATSON_PASSWORD)
    classification = natural_language_classifier.classify(CLASSIFIER_ID_MODELD1, outputString)
    top_classification = classification['top_class']
    temp_classes = classification['classes']
    for i in temp_classes:
        if i['class_name'] == top_classification:
            top_classification_confidence = i['confidence']
    classification_output = [top_classification, top_classification_confidence]
    return classification_output

#gets Actionable/Non-Actionable classification from Watson using model 2
#model 2 is a classification of the pre-processed email body
#this model is supreme court emails
def getClassificationModelS2(email):
    tempString = preprocessGroup2(email.text_body)
    outputString = tempString[:1000]
    #print(outputString)
    natural_language_classifier = NaturalLanguageClassifierV1(
        username=WATSON_USERNAME,
        password=WATSON_PASSWORD)
    classification = natural_language_classifier.classify(CLASSIFIER_ID_MODELS2, outputString)
    top_classification = classification['top_class']
    temp_classes = classification['classes']
    for i in temp_classes:
        if i['class_name'] == top_classification:
            top_classification_confidence = i['confidence']
    classification_output = [top_classification, top_classification_confidence]
    return classification_output

#gets Actionable/Non-Actionable classification from Watson using model 2
#model 2 is a classification of the pre-processed email body
#this is for district court emails
def getClassificationModelD2(email):
    tempString = preprocessGroup1(email.text_body)
    outputString = tempString[:1000]
    #print(outputString)
    natural_language_classifier = NaturalLanguageClassifierV1(
        username=WATSON_USERNAME,
        password=WATSON_PASSWORD)
    classification = natural_language_classifier.classify(CLASSIFIER_ID_MODELD2, outputString)
    top_classification = classification['top_class']
    temp_classes = classification['classes']
    for i in temp_classes:
        if i['class_name'] == top_classification:
            top_classification_confidence = i['confidence']
    classification_output = [top_classification, top_classification_confidence]
    return classification_output

#this will classify the email and update the category using a combination of both classification models
def classifyx(email):
    classification_result_model1 = getClassificationModel1(email)
    classification_result_model2 = getClassificationModel2(email)
    #both models agree on the result and both are above their threshold
    if classification_result_model1[0] == classification_result_model2[0] and classification_result_model1[1] > REQUIRED_CONFIDENCE_MODEL1 and classification_result_model2[1] > REQUIRED_CONFIDENCE_MODEL2:
        try:
            email.categories.append(classification_result_model1[0])
        except:
            email.categories = []
            email.save()
            email.categories.append(classification_result_model1[0])
        average_confidence = ((classification_result_model1[1] + classification_result_model2[1])/2)
        average_confidence_str = str(round(average_confidence,2))
        email.categories.append(average_confidence_str)
        email.save()
    #models disagree on the result
    else:
        model1_class = classification_result_model1[0] + ' M1'
        try:
            email.categories.append(model1_class)
        except:
            email.categories = []
            email.save()
            email.categories.append(model1_class)
        model1_perc = str(round(classification_result_model1[1],2)) + ' M1'
        email.categories.append(model1_perc)
        model2_class = classification_result_model2[0] + ' M2'
        email.categories.append(model2_class)
        model2_perc = str(round(classification_result_model2[1],2)) + ' M2'
        email.categories.append(model2_perc)
        email.save()




#this will classify the email and update the category using a combination of 4 classification models
def classify(email):
    preprocessing_group = identify_email_group(email)
    if preprocessing_group == 'email_group_1':
        classification_result_model1 = getClassificationModelD1(email)
        classification_result_model2 = getClassificationModelD2(email)
    elif preprocessing_group == 'email_group_2':
        classification_result_model1 = getClassificationModelS1(email)
        classification_result_model2 = getClassificationModelS2(email)
    #both models agree on the result and both are above their threshold
    if classification_result_model1[0] == classification_result_model2[0] and classification_result_model1[1] > REQUIRED_CONFIDENCE_MODEL1 and classification_result_model2[1] > REQUIRED_CONFIDENCE_MODEL2:
        try:
            email.categories.append(classification_result_model1[0])
        except:
            email.categories = []
            email.save()
            email.categories.append(classification_result_model1[0])
        average_confidence = ((classification_result_model1[1] + classification_result_model2[1])/2)
        average_confidence_str = str(round(average_confidence,2))
        email.categories.append(average_confidence_str)
        email.save()
    #models disagree on the result
    else:
        model1_class = classification_result_model1[0] + ' M1'
        try:
            email.categories.append(model1_class)
        except:
            email.categories = []
            email.save()
            email.categories.append(model1_class)
        model1_perc = str(round(classification_result_model1[1],2)) + ' M1'
        email.categories.append(model1_perc)
        model2_class = classification_result_model2[0] + ' M2'
        email.categories.append(model2_class)
        model2_perc = str(round(classification_result_model2[1],2)) + ' M2'
        email.categories.append(model2_perc)
        email.save()

#this will classify the email for the testing set and update the category using a combination of 4 classification models
#this should be interchangeable with classify later, this just returns a value and classify doesn't
def classifytest(email):
    preprocessing_group = identify_email_group(email)
    if preprocessing_group == 'email_group_1':
        classification_result_model1 = getClassificationModelD1(email)
        classification_result_model2 = getClassificationModelD2(email)
        process = 'YES'
    elif preprocessing_group == 'email_group_2':
        classification_result_model1 = getClassificationModelS1(email)
        classification_result_model2 = getClassificationModelS2(email)
        process = 'YES'
    else: #this stops processing on unknown email addresses
        process = 'NO'
    if process == 'YES':
    #both models agree on the result and both are above their threshold
        if classification_result_model1[0] == classification_result_model2[0] and classification_result_model1[1] > REQUIRED_CONFIDENCE_MODEL1 and classification_result_model2[1] > REQUIRED_CONFIDENCE_MODEL2:
            try:
                email.categories.append(classification_result_model1[0])
            except:
                email.categories = []
                email.save()
                email.categories.append(classification_result_model1[0])
            average_confidence = ((classification_result_model1[1] + classification_result_model2[1])/2)
            average_confidence_str = str(round(average_confidence,2))
            email.categories.append(average_confidence_str)
            email.save()
            outputString = ('1,' + classification_result_model1[0] + ',' + str(classification_result_model1[1]) + ',2,' +
                            classification_result_model2[0] + ',' + str(classification_result_model2[1]))
            return outputString
        #models disagree on the result
        else:
            model1_class = classification_result_model1[0] + ' M1'
            try:
                email.categories.append(model1_class)
            except:
                email.categories = []
                email.save()
                email.categories.append(model1_class)
            model1_perc = str(round(classification_result_model1[1],2)) + ' M1'
            email.categories.append(model1_perc)
            model2_class = classification_result_model2[0] + ' M2'
            email.categories.append(model2_class)
            model2_perc = str(round(classification_result_model2[1],2)) + ' M2'
            email.categories.append(model2_perc)
            email.save()
            outputString = ('1,' + classification_result_model1[0] + ',' + str(classification_result_model1[1]) + ',2,' +
                            classification_result_model2[0] + ',' + str(classification_result_model2[1]))

            return outputString
    else:
        return 'Unprocessed'




#this will clear the categories from all emails in the inbox
def clearInboxCategories(account):
    counter = 0
    inbox_folder_items = email_account.inbox.all()
    for email in inbox_folder_items:
        ##clear current classification - this is for testing only
        email.categories = []
        email.save()
        counter += 1
    result = 'Cleared the categories of ' + str(counter) + ' emails in the inbox.'
    return result

#This will categorize all emails in the inbox
def categorizeInbox(account):
    counter = 0
    inbox_folder_items = email_account.inbox.all()
    for email in inbox_folder_items:
        ##run combined classification
        classify(email)
        counter += 1
    result = 'Completed the categorization of ' + str(counter) + ' emails in the inbox.'
    return result

#this will take the account object and create training files for all models from the emails in the training subfolders
def createTrainingFiles(email_account,training_file_model_d1,training_file_model_d2,training_file_model_s1,training_file_model_s2,training_folder,subfolder1,subfolder2):
    folder1 = email_account.root.get_folder_by_name(training_folder).get_folder_by_name(subfolder1)
    folder2 = email_account.root.get_folder_by_name(training_folder).get_folder_by_name(subfolder2)
    print(folder1.total_count)
    total_1 = folder1.total_count
    total_2 = folder2.total_count
    print(folder2.total_count)
    modeld1file = open(training_file_model_d1, 'w')
    modeld2file = open(training_file_model_d2, 'w')
    models1file = open(training_file_model_s1, 'w')
    models2file = open(training_file_model_s2, 'w')
    counter = 0
    folder_items_1 = folder1.all()
    for email in folder_items_1:
        tempString1 = ''
        tempString2 = ''
        preprocessing_group = identify_email_group(email)
        if len(email.text_body) > 50:
            tempString1 = formatMailBody(email.text_body)
            if preprocessing_group == 'email_group_1':
                tempString2 = preprocessGroup1(email.text_body)
                if len(tempString1) > 50:
                    outputStringModel1 = tempString1[:1000] + ',' + subfolder1 + '\n'
                    modeld1file.write(outputStringModel1)
                if len(tempString2) > 50:
                    outputStringModel2 = tempString2[:1000] + ',' + subfolder1 + '\n'
                    modeld2file.write(outputStringModel2)
            elif preprocessing_group == 'email_group_2':
                tempString2 = preprocessGroup2(email.text_body)
                if len(tempString1) > 50:
                    outputStringModel1 = tempString1[:1000] + ',' + subfolder1 + '\n'
                    models1file.write(outputStringModel1)
                if len(tempString2) > 50:
                    outputStringModel2 = tempString2[:1000] + ',' + subfolder1 + '\n'
                    models2file.write(outputStringModel2)
        counter = counter + 1
        print('Processed ' + str(counter) + ' of ' + str(total_1) + ' in folder ' + subfolder1)
    counter = 0
    folder_items_2 = folder2.all()
    for email in folder_items_2:
        tempString1 = ''
        tempString2 = ''
        preprocessing_group = identify_email_group(email)
        if len(email.text_body) > 50:
            tempString1 = formatMailBody(email.text_body)
            if preprocessing_group == 'email_group_1':
                tempString2 = preprocessGroup1(email.text_body)
                if len(tempString1) > 50:
                    outputStringModel1 = tempString1[:1000] + ',' + subfolder2 + '\n'
                    modeld1file.write(outputStringModel1)
                if len(tempString2) > 50:
                    outputStringModel2 = tempString2[:1000] + ',' + subfolder2 + '\n'
                    modeld2file.write(outputStringModel2)
            elif preprocessing_group == 'email_group_2':
                tempString2 = preprocessGroup2(email.text_body)
                if len(tempString1) > 50:
                    outputStringModel1 = tempString1[:1000] + ',' + subfolder2 + '\n'
                    models1file.write(outputStringModel1)
                if len(tempString2) > 50:
                    outputStringModel2 = tempString2[:1000] + ',' + subfolder2 + '\n'
                    models2file.write(outputStringModel2)
        counter = counter + 1
        print('Processed ' + str(counter) + ' of ' + str(total_2) + ' in folder ' + subfolder2)
    modeld1file.close()
    modeld2file.close()
    models1file.close()
    models2file.close()
    return 'Done'

#gets classifier info from watson nlc
def getTrainingStatus(classifier_id,username,password):
    natural_language_classifier = NaturalLanguageClassifierV1(
        username=username,
        password=password)

    classifier_info = natural_language_classifier.get_classifier(classifier_id)
    return classifier_info

#deletes a classifer
def deleteClassifier(classifier_id,username,password):
    natural_language_classifier = NaturalLanguageClassifierV1(
        username=username,
        password=password)

    classifier_info = natural_language_classifier.delete_classifier(classifier_id)
    return classifier_info

#prints formatted classifier info for 2 models
def classifierInfo():
    #classifier_info_1 = getTrainingStatus(CLASSIFIER_ID_MODEL1,WATSON_USERNAME,WATSON_PASSWORD)
    #classifier_info_2 = getTrainingStatus(CLASSIFIER_ID_MODEL2,WATSON_USERNAME,WATSON_PASSWORD)
    classifier_info_1 = getTrainingStatus(CLASSIFIER_ID_MODELS1,WATSON_USERNAME,WATSON_PASSWORD)
    classifier_info_2 = getTrainingStatus(CLASSIFIER_ID_MODELS2,WATSON_USERNAME,WATSON_PASSWORD)
    classifier_info_3 = getTrainingStatus(CLASSIFIER_ID_MODELD1,WATSON_USERNAME,WATSON_PASSWORD)
    classifier_info_4 = getTrainingStatus(CLASSIFIER_ID_MODELD2,WATSON_USERNAME,WATSON_PASSWORD)
    classifier_info_5 = getTrainingStatus(CLASSIFIER_ID_CATEGORIZE,WATSON_USERNAME,WATSON_PASSWORD)
    print('ClASSIFIER S1')
    print(classifier_info_1['classifier_id'])
    print(classifier_info_1['name'])
    print(classifier_info_1['status'])
    print(' ')
    print('ClASSIFIER S2')
    print(classifier_info_2['classifier_id'])
    print(classifier_info_2['name'])
    print(classifier_info_2['status'])
    print(' ')
    print('ClASSIFIER D1')
    print(classifier_info_3['classifier_id'])
    print(classifier_info_3['name'])
    print(classifier_info_3['status'])
    print(' ')
    print('ClASSIFIER D2')
    print(classifier_info_4['classifier_id'])
    print(classifier_info_4['name'])
    print(classifier_info_4['status'])
    print(' ')
    print('ClASSIFIER CATEGORIZATION')
    print(classifier_info_5['classifier_id'])
    print(classifier_info_5['name'])
    print(classifier_info_5['status'])


def createModelAnalysis(output_file, email_account):
    # THIS ONLY PROCESSES EMAILS IN TESTING/ACTIONABLE AND TESTING/NON-ACTIONABLE
    # open output file
    AnalysisOutputFile = open(output_file, 'w')

    # get testing folders
    actionable_folder = email_account.root.get_folder_by_name('Testing').get_folder_by_name('actionable')
    nonactionable_folder = email_account.root.get_folder_by_name('Testing').get_folder_by_name('non-actionable')
    actionable_folder_count = actionable_folder.total_count
    print("Test Actionable Emails Folder ", actionable_folder_count)
    actionable_emails = actionable_folder.all()
    completed = 0
    for email in actionable_emails[:1000]:
        email.categories = []
        email.save()
        result = classifytest(email)
        from_add = email.author.email_address
        from_add = from_add.lower()
        outputString = (from_add + ',actionable,' + result)
        print(outputString)
        AnalysisOutputFile.write(outputString + '\n')
        completed = completed + 1
        print(completed)
    print('Completed processing ', completed, ' actionable emails')
    # print('Actionable ', actionable_count)
    # print('Non-Actionable ', nonactionable_count)
    # print('No Consensus ', noconsensus_count)

    noconsensus_count = 0
    actionable_count = 0
    nonactionable_count = 0
    nonactionable_emails = nonactionable_folder.all()
    nonactionable_folder_count = nonactionable_folder.total_count
    completed = 0
    print("Test Non-Actionable Emails Folder ", nonactionable_folder_count)
    for email in nonactionable_emails[:1000]:
        email.categories = []
        email.save()
        result = classifytest(email)
        from_add = email.author.email_address
        from_add = from_add.lower()
        outputString = (from_add + ',nonactionable,' + result)
        print(outputString)
        AnalysisOutputFile.write(outputString + '\n')
        completed = completed + 1
        print(completed)
    print('Completed processing ', completed, ' emails')
    print('Completed processing ', completed, ' non-actionable emails')

    AnalysisOutputFile.close()

#def generate Email Category Training File
def createCategoryTrainingFile(categories_training_file):
    ctfile = open(categories_training_file, 'w')
    for category in email_categories:
        for property in email_categories[category]:
            value = email_categories[category][property]
            if property =='keywords':
                #print('Category = ', category)
                #print('Property = ', property)
                #print('Value = ', value)
                for entry in value:
                    temp_string = entry + ',' + category + '\n'
                    #print(temp_string)
                    ctfile.write(temp_string)
    ctfile.close()
    return('Created categories training file at ',categories_training_file)


###########################
# MAIN PROCESSING SECTION #
###########################


#connects to exchange - must do this before accessing emails/folders
#email_account = getEmailObject(EMAIL_USERNAME,EMAIL_PASSWORD,EMAIL_SERVER,EMAIL_SMTP)
#print("Inbox Emails ", email_account.inbox.total_count)

#THIS RESETS THE INBOX TO HAVE NO CATEGORIZATIONS
#result = clearInboxCategories(email_account)
#print(result)

#THIS CLASSIFIES EVERYTHING IN THE INBOX
#result = categorizeInbox(email_account)
#print(result)

#THIS CREATES TRAINING FILES
#result = createTrainingFiles(email_account,TRAINING_FILE_MODEL_D1,TRAINING_FILE_MODEL_D2,TRAINING_FILE_MODEL_S1,TRAINING_FILE_MODEL_S2,TRAINING_FOLDER,TRAINING_SUBFOLDER1,TRAINING_SUBFOLDER2)
#print(result)
#result = createCategoryTrainingFile(TRAINING_FILE_CATEGORIES)
#print(result)

#THIS GETS THE STATUS' OF THE MODELS AND PRINTS THEM
#print(deleteClassifier('718eedx290-nlc-456',WATSON_USERNAME,WATSON_PASSWORD))
classifierInfo()


#ANALYZE AGAINST CURRENT MODELS (4 Models)
#createModelAnalysis(RESULT_ANALYSIS_FILE,email_account)

#print(email_categories)
#for category in email_categories['categories']:
#    print(category)
#    print(email_categories['categories'][category])
#    print(email_categories['categories'][category]['critical'])
#    print(email_categories['categories'][category]['keywords'])
#    for keyword in email_categories['categories'][category]['keywords']:
#        print(keyword)
#    print('')

#for category in email_categories['categories']:
#    print(category)
#    for property in email_categories['categories'][category]:
#        print(property)
#        print(email_categories['categories'][category][property])













