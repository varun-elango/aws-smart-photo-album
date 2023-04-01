import json
import time
import boto3
import requests
# Hello
ES_HOST = 'https://search-photos-x265xwykkjszvgjbb6752wl2bi.us-east-1.es.amazonaws.com'
REGION = 'us-east-1'

job_name = ""

def get_url(es_index, es_type):
    url = ES_HOST + '/' + es_index + '/' + es_type + '/_search'
    return url


def get_slots_from_lex(query):
    lex = boto3.client('lex-runtime')
    
    # AWS Lex 
    print("query:{}".format(query))
    lex_response = lex.post_text(
        botName='ImageSearchBot',
        botAlias='dev',
        inputText=query,
        userId='12345'
    )
    print("Lex response: {}".format(json.dumps(lex_response)))
    if "slots" in lex_response.keys():
        slots = lex_response['slots'], True
    else:
        slots = {}, False
    return slots


def get_image_list(slots):
    headers = {"Content-Type": "application/json"}
    img_list = []
    for i, tag in slots.items():
        if tag:
            url = get_url('photoalbum', '_doc')
            print("ES URL --- {}".format(url))
            query = {
                "size": 25,
                "query": {
                    "multi_match": {
                        "query": tag,
                    }
                }
            }

            es_response = requests.get(url, headers=headers, auth=('varun', 'Alpha*123'),
                                      data=json.dumps(query)).json()

            print(es_response)

            es_src = es_response['hits']['hits']
            print("ES HITS --- {}".format(json.dumps(es_src)))
            object_keys = set()
            for photo in es_src:
                labels = [word.lower() for word in photo['_source']['labels']]
                if tag.lower() in labels:
                    object_key = photo['_source']['objectKey']
                    if object_key not in object_keys:
                        object_keys.add(object_key)
                        img_url = object_key
                        # img_url = 'https://photos-59.s3.us-east-1.amazonaws.com/' + object_key
                        img_list.append(img_url)
    return img_list


def build_response(code, body):
    return {
        'statusCode': code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET, POST, PUT',
            'Access-Control-Allow-Headers': 'Content-Type'
        },
        'body': json.dumps(body)
    }

def lambda_handler(event, context):
    # recieve from API Gateway
    print("EVENT --- {}".format(json.dumps(event)))

    global job_name
    # return {
    #     'statusCode': 200,
    #     'body': json.dumps('Hello from Lambda!')
    # }
    query_params = event["queryStringParameters"]
    if not query_params:
        return build_response(400, "Bad request, there was nothing in the query params")
    query = query_params["q"]
    print("QueryStringParameters: ----" , query)
    
    # AWS Transcribe: Get transcribed text from voice recordings
    if (query == "transcriptionStart"):
        transcribe = boto3.client('transcribe')
        job_name = time.strftime("%a %b %d %H:%M:%S %Y", time.localtime()).replace(":", "-").replace(" ", "")
        storage_uri = "transcriptionnotes"
        job_uri = "https://s3.amazonaws.com/transcriptionnotes/test.wav"
        transcribe.start_transcription_job(
            TranscriptionJobName=job_name,
            Media={'MediaFileUri': job_uri},
            MediaFormat='wav',
            LanguageCode='en-US',
            OutputBucketName=storage_uri
        )
        while True:
            status = transcribe.get_transcription_job(TranscriptionJobName=job_name)
            if status['TranscriptionJob']['TranscriptionJobStatus'] in ['COMPLETED', 'FAILED']:
                break
            print("Transcription not ready yet!")
            time.sleep(5)
        print("Transcript URL: ", status)
        transcriptURL = status['TranscriptionJob']['Transcript']['TranscriptFileUri']
        trans_text = requests.get(transcriptURL).json()
        
        print("Transcripts: ", trans_text)
        print(trans_text["results"]['transcripts'][0]['transcript'])
        
        s3client = boto3.client('s3')
        response = s3client.delete_object(
            Bucket='transcriptionnotes',
            Key='test.wav'
        )
        query = trans_text["results"]['transcripts'][0]['transcript']
        s3client.put_object(Body=query, Bucket='transcriptionnotes', Key='test.wav')
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST, PUT',
                'Access-Control-Allow-Headers': 'Content-Type'
            },
            'body': "Transcription completed"
        }
    
    if (query == "transcriptionEnd"):
        s3client = boto3.client('s3')
        jb_name = job_name + '.json'
        print("Job name: ", jb_name)
        
        # Get Transcription (JSON) from s3 bucket
        s3 = boto3.resource('s3')
        obj = s3.Object('transcriptionnotes', jb_name)
        body = obj.get()['Body'].read()  
        
        dat = body.decode('utf8').replace("'", '"')
        data = json.loads(dat)
        query = data["results"]["transcripts"][0]["transcript"]
        
        print("Voice query: ", query)
        s3client.delete_object(
            Bucket='transcriptionnotes',
            Key='test.wav'
        )
    
    slots, valid = get_slots_from_lex(query)
    if not valid:
        build_response(200, "I could not understand what you want")
    img_list = get_image_list(slots)
    print("img_list:{}".format(img_list))
    if img_list:
        return build_response(200, img_list)
    else:
        return build_response(200,
                       "There were no photos matching the categories you were looking for.")
