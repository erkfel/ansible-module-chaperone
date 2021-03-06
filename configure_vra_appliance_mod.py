#!/usr/bin/python
#
#  Copyright 2015 VMware, Inc.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

import httplib
import base64
import sys
import xml.dom.minidom as minidom
import time
import logging

DOCUMENTATION = '''
---
module: configure_vra_appliance.py
Short_description: Module for setting vra appliance configuration
description: Module for setting vra appliance configuration which includes
-Time server
-host settings
-SSL cerificate (generation of a certificate for now)
version_added: "1.0"
options:
    vra_host_name:
        description:
            - hostname resolvable by DNS or Ip address of the vra appliance.
        required: True
    vra_port:
        description:
            - port where the VRA listens. Usually 5480
        required: True
    vra_user:
        description:
            - user for the vra appliance configuration. Usually root
        required: True
    vra_root_password:
        description:
            - password for vra_user
        required: True
    vra_ssl_org:
        description:
            - Organization for ssl certificate
        required: True
    vra_ssl_org_unit:
        description:
            - Org unit for ssl certificate
        required: True
    vra_ssl_country:
        description:
            - Country for ssl certificate
        required: True
'''

EXAMPLES = '''
- name: configure_vra_appliance
  configure_vra_appliance_mod:
    vra_host_name: "{{ vra_host_name }}"
    vra_root_password: "{{ vra_root_password }}"
    vra_port: "{{ vra_port }}"
    vra_ssl_org: "{{ vra_ssl_org }}"
    vra_ssl_org_unit: "{{ vra_ssl_org_unit }}"
    vra_ssl_country: "{{ vra_ssl_country }}"
'''


class VRAConfigSettor:

    masterout = ""

    def _init_(self):
        self.vra_host_name= ""
        self.vra_root_password = ""
        self.vra_host_port=""

        self.vra_ssl_org=""
        self.vra_ssl_org_unit=""
        self.vra_ssl_country=""
        self.vra_ntp_server = ""

    def initializeHost(self, hostname, password, vra_host_port):
        self.vra_host_name= hostname
        self.vra_root_password = password
        self.vra_host_port=vra_host_port

    def initializeSSLSettings(self, vra_ssl_org, vra_ssl_org_unit, vra_ssl_country):
        self.vra_ssl_org=vra_ssl_org
        self.vra_ssl_org_unit=vra_ssl_org_unit
        self.vra_ssl_country=vra_ssl_country

    def initializeNTPSettings(self,vra_ntp_server):
        self.vra_ntp_server=vra_ntp_server

    #todo pass in id and thus make this method generic
    def parseResponseToSeeIfHostSettingsArePresent(self, xmlResponse):

        #iterate lines
        xmldoc = minidom.parseString(xmlResponse)
        itemlist = xmldoc.getElementsByTagName('value')

        hostSettingFound=False
        sslSettingsFound=False
        for s in itemlist:
            id = ""
            value = ""
            id=s.attributes['id'].value


            childNodes=s.childNodes
            if( (childNodes is not None) and (len(childNodes) !=0) ):
                value=s.childNodes[0].data
                value = value[0:20]

            if("cafe.host" in id) and (value != ""):
                logging.debug("vra host setting found")
                hostSettingFound = True

            if("ssl.key" in id) and (value != "") and (len(value)>5) :
                logging.debug("vra ssl key setting found. it is:" + str(value))
                sslSettingsFound = True

        if(hostSettingFound == False):
            self.addToResultMessage("vra host setting NOT found")
            return False

        if(sslSettingsFound == False):
            self.addToResultMessage("vra ssl settings NOT found")
            return False

        return True


    #todo pass in id and thus make this method generic
    def parseResponseToGetValue(self, xmlResponse, idkey):

        #iterate lines
        xmldoc = minidom.parseString(xmlResponse)
        itemlist = xmldoc.getElementsByTagName('value')

        found_value=None
        for s in itemlist:
            id = ""
            value = ""
            id=s.attributes['id'].value


            childNodes=s.childNodes
            if( (childNodes is not None) and (len(childNodes) !=0) ):
                value=s.childNodes[0].data
                value = value[0:20]

            if(idkey in id):
                found_value=value

        if(found_value is not None):
            return found_value

        logging.debug("Parsed value for id from xml is None")
        return None


    def getvRA(self, vRAInstance):
        conn = httplib.HTTPSConnection(vRAInstance, 5480)
        headers = {"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8", "Cache-Control": "no-cache"}
        try:
            conn.request('GET', "/#core.Login", "", headers)
            response = conn.getresponse()
            conn.close()
        except Exception as e:
            self.addToResultMessage("Error connecting to vra instance")
            return False

        return (response.status == 200) and (response.reason == 'OK')

    def getvRAAuthToken(self, vRAInstance, vRARootPassword):
        logging.debug("Obtaining auth token")
        token = None
        conn = httplib.HTTPSConnection(vRAInstance, 5480)
        credentialString = "root:"  + vRARootPassword
        credentialStringBytes = credentialString.encode()
        encodedCreds = base64.encodestring(credentialStringBytes).decode().replace('\n','')
        headers = {"Authorization": "Basic " + encodedCreds, "Accept": "text/html, text/xml, application/xml", "Cache-Control": "no-cache", "Accept-Encoding": "gzip, deflate", "Accept-Language": "en-US,en;q=0.8,pt;q=0.6", "Connection":"keep-alive", "Content-type":"application/xml; charset=\"UTF-8\""}
        requestPayload = """<?xml version="1.0" encoding="UTF-8"?>
        <CIM CIMVERSION="2.0" DTDVERSION="2.0"><MESSAGE ID="5" PROTOCOLVERSION="1.0"><SIMPLEREQ><METHODCALL NAME="CreateSessionToken"><LOCALCLASSPATH><LOCALNAMESPACEPATH><NAMESPACE NAME="root"/><NAMESPACE NAME="cimv2"/></LOCALNAMESPACEPATH><CLASSNAME NAME="VAMI_Authentication"/></LOCALCLASSPATH></METHODCALL></SIMPLEREQ></MESSAGE></CIM>"""
        conn.request('POST', "/cimom", requestPayload, headers)
        response = conn.getresponse()
        status = response.status
        if ( status == 200 and response.reason == 'OK'):
            xmlResponse = response.read().decode(encoding='UTF-8')
            logging.debug("xmlResponse for token is: " + xmlResponse)
            lines = xmlResponse.splitlines()
            for line in lines:
                if '<VALUE>' in line:
                    value = line.replace("<VALUE>", "")
                    value = value.replace("</VALUE>", "")
                    if value != '0':
                        token = value
                        break
        else:
            self.addToResultMessage("Error code: " + str(status))
        conn.close()
        logging.debug("token is: " + token)
        return token

    def httpPost(self, vRAInstance, token, url, requestpayload, print_xml):
        conn = httplib.HTTPSConnection(vRAInstance, 5480)
        credentialString = "root:" + token
        credentialStringBytes = credentialString.encode()
        encodedCreds = base64.encodestring(credentialStringBytes).decode().replace('\n','')
        headers = {"Authorization": "Basic " + encodedCreds, "Content-Type": "text/plain;charset=UTF-8"}

        if(print_xml == True):
            self.addToResultMessage("CONSTRUCTED Payload for SSO configure post is:")
            self.addToResultMessage(requestpayload)

        conn.request('POST', url, requestpayload, headers)
        response = conn.getresponse()
        status = response.status
        reason = response.reason
        xmlResponse = response.read().decode(encoding='UTF-8')

        if(print_xml == True):
            self.addToResultMessage("Post Response is:")
            self.addToResultMessage(xmlResponse)

        conn.close()
        if(status == 200 and reason == 'OK'):
            logging.debug("Http post call returned successfully.")
            return True
        else:
            self.addToResultMessage("Error during a configure vra call. Error code: " + str(status))
            return False

    def configureNTPSetting(self,token):

        vra_host_name=self.vra_host_name
        vra_ntp_server=self.vra_ntp_server
        requestPayload = """<?xml version="1.0" encoding="utf-8"?>
                            <request>
                                <locale>en-US</locale>
                                <action>submit</action>
                                <requestid>ntpUpdate</requestid>
                                <value id="ntp.sync-mode">server</value>"""
        requestPayload += "<value id=\"ntp.host1\">" + vra_ntp_server + "</value>\n"
        requestPayload += """</request>"""
        url = "/service/administration/config-page.py"
        print_xml = False
        success=self.httpPost(vra_host_name, token, url, requestPayload, print_xml)
        if(success):
            self.addToResultMessage("NTP server setting set successfully")
        else:
            self.addToResultMessage("NTP server setting NOT set successfully")

    def configureHostAndSSL(self, token):

        vRAInstance = self.vra_host_name
        vra_host_port=self.vra_host_port

        vra_ssl_org=self.vra_ssl_org
        vra_ssl_org_unit=self.vra_ssl_org_unit
        vra_ssl_country=self.vra_ssl_country

        conn = httplib.HTTPSConnection(vRAInstance, vra_host_port)
        credentialString = "root:" + token
        credentialStringBytes = credentialString.encode()
        encodedCreds = base64.encodestring(credentialStringBytes).decode().replace('\n','')
        headers = {"Authorization": "Basic " + encodedCreds, "Content-Type": "text/plain;charset=UTF-8"}
        requestPayload = """<?xml version="1.0" encoding="utf-8"?>
                            <request>
                                <locale>en-US</locale>
                                <action>submit</action>
                                <requestid>serverUpdate</requestid>
                                <value id="host.type">resolve</value>"""

        requestPayload += "<value id=\"cafe.host\">" + vRAInstance + "</value>\n"

        requestPayload += "<value id=\"ssl.commonName\">" + vRAInstance + "</value>\n"

        #Not required in vRA 7.0 or Import cert?
        requestPayload += """<value id="ssl.action">generate</value>
                             <value id="ssl.organization">VMwareIncorp</value>
                                <value id="ssl.organizationalUnit">PSO TX</value>
                                <value id="ssl.country">US</value>
                                <value id="ssl.encoded.key"></value>
                                <value id="ssl.encoded.cert"></value>
                                <value id="ssl.passphrase"></value>
                            </request>
                          """

        logging.debug("ABOUT TO CALL POST FOR HostSettings and SSL")

        conn.request('POST', "/service/cafe/config-page.py", requestPayload, headers)

        response = conn.getresponse()
        status = response.status
        reason = response.reason
        conn.close()
        if ( status == 200 and reason == 'OK'):
            self.addToResultMessage("Host and certificate configured successfully")
            return True
        else:
            self.addToResultMessage("Error code: " + str(status))
        return False

    def getXMLForHostAndSSLConfigFromVRA(self, vRAInstance, token):

        conn = httplib.HTTPSConnection(vRAInstance, 5480)
        credentialString = "root:" + token
        credentialStringBytes = credentialString.encode()
        encodedCreds = base64.encodestring(credentialStringBytes).decode().replace('\n','')
        headers = {"Authorization": "Basic " + encodedCreds, "Content-Type": "text/plain;charset=UTF-8"}
        requestPayload = """<?xml version="1.0" encoding="utf-8"?>
                            <request>
                            <locale>en-US</locale>
                            <action>submit</action>
                            <requestid>serverInfo</requestid>
                            </request>
                        """

        logging.debug("payload is:" + requestPayload)
        logging.debug("Calling http post to get HostSettings and SSL")

        conn.request('POST', "/service/cafe/config-page.py", requestPayload, headers)
        response = conn.getresponse()
        xmlResponse = response.read().decode(encoding='UTF-8')
        status = response.status
        reason = response.reason
        conn.close()
        if ( status == 200 and reason == 'OK'):
            self.addToResultMessage("GOT host settings and SSL config")
            return xmlResponse

        else:
            self.addToResultMessage("Error code: " + str(status))
            return None

    def checkHostAndSSLConfig(self, vRAInstance, token):

        xmlResponse = self.getXMLForHostAndSSLConfigFromVRA(vRAInstance, token)
        if( xmlResponse is not None):
            found = self.parseResponseToSeeIfHostSettingsArePresent(xmlResponse)
            return found
        else:
            self.addToResultMessage("No xml response for Host setting and ssl. Assuming not set")
            return False

    def addToResultMessage(self, msg):
        logging.debug(msg)
        self.masterout = self.masterout + msg + ". "

    def execute(self):

        vra_host_name=self.vra_host_name
        vra_root_password=self.vra_root_password
        timeForLogin=-1
        timeForFetchingHostSettings=-1
        timeForHostSettings=-1
        timeForNTPSettings=-1

        execute_start = time.time()

        logging.debug("In the anisible python module for vra Configure Settings")
        self.addToResultMessage("vra host is: " + vra_host_name)

        if(self.getvRA(vra_host_name)):
            logging.debug("Your vRA deployment " + vra_host_name + " is accessible")
        else:
            outmsg = "Your vRA deployment " + vra_host_name + " is NOT accessible"
            logging.error(outmsg)
            return False, outmsg


        start = time.time()
        token = self.getvRAAuthToken(vra_host_name, vra_root_password)
        end = time.time()
        timeForLogin = end - start

        if(token != None):
            self.addToResultMessage("Login successful ")
        else:
            self.addToResultMessage("Login not successful ")
            return False, "Login not successful "

        start = time.time()
        logging.debug("call to : get hostname and ssl config")
        hostSettingSet = self.checkHostAndSSLConfig(vra_host_name, token)
        logging.debug("done with call to : get hostname and ssl config")
        end = time.time()
        timeForFetchingHostSettings = end - start

        logging.debug("Configuring the hostname and generating a self signed certificate")
        if(hostSettingSet == False):
            self.addToResultMessage("Setting host and ssl as they are NOT set")
            start = time.time()
            self.configureHostAndSSL(token)
            end = time.time()
            timeForHostSettings = end - start
        else:
            self.addToResultMessage("Bypassing setting host and ssl as they are already set")

        start = time.time()
        self.configureNTPSetting(token)
        end = time.time()
        timeForNTPSettings = end - start

        self.addToResultMessage("Done with all of the vra configure steps")
        self.addToResultMessage("Time for login: " + str(round(timeForLogin,2)))
        self.addToResultMessage("Time for fetching host settings: " + str(round(timeForFetchingHostSettings,2)))
        self.addToResultMessage("Time for host settings: " + str(round(timeForHostSettings,2)))
        self.addToResultMessage("Time for NTP settings: " + str(round(timeForNTPSettings,2)))

        execute_end = time.time()
        totalTimeForExecute = execute_end - execute_start
        self.addToResultMessage("Total Time for all settings: " + str(round(totalTimeForExecute,2)))

        return True, self.masterout




def main():

    logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')
    module = AnsibleModule(
        argument_spec = dict(
            vra_host_name = dict(required=True),
            vra_root_password = dict(required=True),
            vra_port=dict(required=True),

            vra_ssl_org=dict(required=True),
            vra_ssl_org_unit=dict(required=True),
            vra_ssl_country=dict(required=True),
            vra_ntp_server=dict(required=True)

        )
    )

    vra_host_name= module.params['vra_host_name']
    vra_root_password = module.params['vra_root_password']
    vra_host_port= module.params['vra_port']

    vra_ssl_org=module.params['vra_ssl_org']
    vra_ssl_org_unit=module.params['vra_ssl_org_unit']
    vra_ssl_country=module.params['vra_ssl_country']

    vra_ntp_server=module.params['vra_ntp_server']

    try:
        settor = VRAConfigSettor()

        settor.initializeHost(vra_host_name, vra_root_password, vra_host_port)
        settor.initializeSSLSettings(vra_ssl_org, vra_ssl_org_unit, vra_ssl_country)
        settor.initializeNTPSettings(vra_ntp_server)

        success, output  = settor.execute()

    except Exception as e:
        import traceback
        module.fail_json(msg = '%s: %s\n%s' %(e.__class__.__name__, str(e), traceback.format_exc()))

    #comment next 4 lines if you want to not do a normal exit to ansible BUT see python print statements
    if success:
        module.exit_json(changed=True, msg=output)
    else:
        module.fail_json(msg=output)


from ansible.module_utils.basic import *
from ansible.module_utils.facts import *
main()