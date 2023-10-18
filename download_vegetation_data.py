import requests
import click 
import time 
import zipfile
import json
import os
import shutil

import lxml.html


@click.command()
@click.option(
    "--bbox",
    default="-124.566244,46.864746,-116.463504,41.991794",
    help="Bounding box to download data for",
)
def cli(bbox):

    if not os.path.exists("data/landfire_vegetation"):
        os.makedirs("data/landfire_vegetation")
    else:
        # delete the existing files and make it again
        shutil.rmtree("data/landfire_vegetation")
        os.makedirs("data/landfire_vegetation")
        
    # get the layer values csv 
    print("Downloading layer values csv...")
    url = "https://landfire.gov/CSV/LF2022/LF22_EVT_230.csv"
    response = requests.get(url)
    with open("data/landfire_vegetation/values.csv", "wb") as f:
        f.write(response.content)

    print("Submitting job to Landfire API...")

    # see https://lfps.usgs.gov/helpdocs/productstable.html for layer list
    host = "https://lfps.usgs.gov"
    dataset = "230EVT" # 2022 existing vegetation type 
    bbox = bbox.replace(",", " ")
    url = "{}/arcgis/rest/services/LandfireProductService/GPServer/LandfireProductService/submitJob?Layer_List={}&Area_Of_Interest={}".format(host, dataset, bbox)
    
    job_url = None

    try:
        response = requests.get(url)
        tree = lxml.html.fromstring(response.text)
        
        # get the second to last href
        job_url = tree.xpath('//a/@href')[-2]

        print("Submitted job...")
        time.sleep(4)

    except Exception as e:
        print("Failed to submit job to Landfire API")
        print(e)


    working = True

    if job_url:
        while working:
            try:
                print("Checking job status...")
                response = requests.get(host + job_url)
                tree = lxml.html.fromstring(response.text)
                error_msgs = tree.xpath('//body//text()[contains(., "esriJobFailed")]')
                if len(error_msgs) > 0:
                    print("Job failed")
                    # print the text content of the last ul element on the page, containing error messages
                    trace = tree.xpath('//ul[last()]//text()')
                    for line in trace:
                        print(line)
                    working = False
                    break
                else:
                    complete_msgs = tree.xpath('//body//text()[contains(., "esriJobSucceeded")]')
                    if len(complete_msgs) > 0:
                        try:
                            print("Job complete")
                            # search for the href with content "Output_File"
                            output_url = tree.xpath('//a[text()="Output_File"]/@href')[0]
                            print("Downloading output file...")
                            response = requests.get(host + output_url)
                            tree = lxml.html.fromstring(response.text)
                            # get the content of the last pre element on the page
                            pre = tree.xpath('//pre[last()]//text()')[0]
                            json_response = json.loads(pre)
                            zip_file = json_response['value']['url']

                        except Exception as e:
                            print("Failed to get zipfile url")
                            print(e)
                            working = False
                            break

                        try:
                            # dowload the zipfile
                            response = requests.get(zip_file)
                            # save the zipfile
                            with open("data/landfire_vegetation.zip", "wb") as f:
                                f.write(response.content)
                        except Exception as e:
                            print("Failed to download zipfile")
                            print(e)
                            working = False
                            break

                        try: 
                            print("Unzipping zipfile...")
                            with zipfile.ZipFile("data/landfire_vegetation.zip", "r") as zip_ref:
                                zip_ref.extractall("data/landfire_vegetation")
                        except Exception as e:
                            print("Failed to unzip zipfile")
                            print(e)
                            working = False
                            break

                        print("Done!")
                        working = False
                        break
                    else:
                        print("Job still running, waiting...")
                        time.sleep(4)
                
            except Exception as e:
                print("Failed to get job status")
                print(e)


if __name__ == "__main__":
    cli()