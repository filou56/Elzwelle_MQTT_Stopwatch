package main

import (
	"log"
	"fmt"
	"io/ioutil"
	"time"
	"gopkg.in/Iwark/spreadsheet.v2"
	"golang.org/x/net/context"
	"golang.org/x/oauth2/google"
	"flag"
	mqtt "github.com/eclipse/paho.mqtt.golang"
	"net/url"
	"strings"
	"util"
	"mqttpipe"
)

var (
	mqttHost 		string 	= "localhost"
	mqttTopic 		string 	= "stopwatch"
	mqttCommit		bool	= false
	receive 		chan mqtt.Message
)

//------------------------- MQTT ------------------------
func mqttConnect(clientId string, uri *url.URL) mqtt.Client {
	opts := mqttClientOptions(clientId, uri)
	client := mqtt.NewClient(opts)
	token := client.Connect()
	for !token.WaitTimeout(3 * time.Second) {
	}
	if err := token.Error(); err != nil {
		log.Fatal("Sheet:\t",err)
	}
	return client
}

func mqttClientOptions(clientId string, uri *url.URL) *mqtt.ClientOptions {
	opts := mqtt.NewClientOptions()
	
	opts.AddBroker(fmt.Sprintf("tcp://%s", uri.Host))
//  ---------- Options -------------	
//	opts.SetUsername(uri.User.Username())
//	password, _ := uri.User.Password()
//	opts.SetPassword(password)
//	opts.SetClientID(clientId)
	opts.SetPingTimeout(10 * time.Second)
	opts.SetKeepAlive(10 * time.Second)
	opts.SetAutoReconnect(true)
//	opts.SetMaxReconnectInterval(10 * time.Second)
//  --------------------------------

	opts.SetConnectionLostHandler(func(c mqtt.Client, err error) {
		log.Printf("Sheet:\tMQTT connection lost error: %s\n" + err.Error())
	})
	
	opts.SetReconnectingHandler(func(c mqtt.Client, options *mqtt.ClientOptions) {
		log.Println("Sheet:\tMQTT reconnecting")
	})
	
	opts.SetDefaultPublishHandler(mqttReceive)
	
	opts.SetOnConnectHandler(func(c mqtt.Client) {
        log.Printf("Sheet:\tClient connected, subscribing to: sheet/#\n")
        //Subscribe here, otherwise after connection lost, you may not receive any message
        if token := c.Subscribe(fmt.Sprintf(mqttTopic+"/#",), 0, nil); token.Wait() && token.Error() != nil {
            log.Println("Sheet:\t",token.Error())
            // TODO handle Error
        }
    })
	return opts
}

func mqttReceive(client mqtt.Client, msg mqtt.Message) {
	log.Printf("Sheet:\tMQTT received [%s] %s\n", msg.Topic(), string(msg.Payload()))
	if strings.Contains(msg.Topic(),mqttTopic+"/data") {
		receive <- msg
	}
}

func main() {
	flag.StringVar(&mqttHost,"mqtt", "//localhost:1883/", "MQTT Host")
	flag.StringVar(&mqttTopic,"topic", "stopwatch", "MQTT Topic")
	flag.BoolVar(&mqttCommit,"commit", false, "MQTT Commit")
	
	flag.Parse()
	
	// -------------- MQTT --------------
	uri, err := url.Parse(mqttHost)
	if err != nil {
		log.Fatal("Sheet:\tMQTT: ",err)
	}
			
	receive = make (chan mqtt.Message,100)	
		
	mqttClient := mqttConnect("GOOGLE_SHEET_XX", uri)
	defer mqttClient.Disconnect(0)
		
	mqttpipe.Send = make(chan mqttpipe.Message, 100)
	defer close(mqttpipe.Send)
	
	go mqttpipe.Sender(mqttClient)
		
	data, err := ioutil.ReadFile("client_secret.json")
	checkError(err)
	conf, err := google.JWTConfigFromJSON(data, spreadsheet.Scope)
	checkError(err)
	client := conf.Client(context.TODO())
	client.Timeout = 5 * time.Second
	
	log.Println("Sheet:\tNew Service")
	service := spreadsheet.NewServiceWithClient(client)
	spreadsheet, err := service.FetchSpreadsheet("1M05W0igR6stS4UBPfbe7-MFx0qoe5w6ktWAcLVCDZTE")
	checkError(err)

	log.Println("Sheet:\tFetch Spreadsheet")
	startSheet,  err := spreadsheet.SheetByIndex(0)
	finishSheet, err := spreadsheet.SheetByIndex(1)
	checkError(err)
	
	startIdx  := len(startSheet.Rows)
	finishIdx := len(finishSheet.Rows)

	log.Println("Sheet:\tUpdate Loop")

	client.Timeout = 5 * time.Second

	if mqttCommit { mqttpipe.Send <- mqttpipe.Message{"stopwatch/commit",[]byte("START")} }
	time.Sleep(2 * time.Second)

	loop := true
	
	for loop {
		msg := <- receive
		log.Println("Sheet:\tReceive")
		if strings.Contains(msg.Topic(),mqttTopic+"/data") {
			var items map[string]interface{}		
			items = util.DecodePayload(msg.Payload())
			//util.DumpMap("",items)
			if len(items) == 3 {
				if (items["Channel"] != nil) { 
					valid := true
					channel := 0
					switch items["Channel"].(type) {
					case float64 :
						channel = int(items["Channel"].(float64))
						if (items["Time"] != nil) { 
							switch items["Time"].(type) {
							case string :
								//Receive <- StopwatchMessage{channel,items["Timestamp"].(string)}
								now := items["Time"].(string)
								if channel == 1 {
									// Update cell content
									startSheet.Update(startIdx, 0, now)		
								} else if channel == 2 {
									// Update cell content
									finishSheet.Update(finishIdx, 0, now)		
								} else {
									log.Println("Sheet:\tErrro Channel Time")
									valid = false
								}		
							}
						} else {
							valid = false
						}		
						if (items["Stamp"] != nil) { 
							switch items["Stamp"].(type) {
							case float64 :
								//Receive <- StopwatchMessage{channel,items["Timestamp"].(string)}
								stamp := items["Stamp"].(float64)
								if channel == 1 {
									// Update cell content
									startSheet.Update(startIdx, 1, fmt.Sprintf("%4.2f",stamp))		
								} else if channel == 2 {
									// Update cell content
									finishSheet.Update(finishIdx, 1, fmt.Sprintf("%4.2f",stamp))		
								} else {
									log.Println("Sheet:\tErrro Channel Stamp")
									valid = false
								}		
							}
						} else {
							valid = false
						}
					}
					if valid {
						if channel == 1 {
							err = startSheet.Synchronize()
							if err == nil { startIdx = startIdx + 1 }
						} else if channel == 2 {
							err = finishSheet.Synchronize()
							if err == nil { finishIdx = finishIdx + 1 }
						} 
						if err != nil {
							log.Println("Sheet:\tError 0:",err)
							if mqttCommit { mqttpipe.Send <- mqttpipe.Message{"stopwatch/commit",[]byte("BREAK")} }
							time.Sleep(2 * time.Second)
							loop = false
						} else {
							//log.Println("Sheet:\tUpdate 0:",msg)
							if mqttCommit { mqttpipe.Send <- mqttpipe.Message{"stopwatch/commit",msg.Payload()} }
						}
					} else {
						if mqttCommit { mqttpipe.Send <- mqttpipe.Message{"stopwatch/commit",[]byte("ERROR 1")} }
					}
				}
			} 		
		} 
	}
//	for loop {
//		msg := <- receive
//		
//		if strings.Contains(msg.Topic(),"sheet/data") {
//			var items map[string]interface{}		
//			items = util.DecodePayload(msg.Payload())
//			//util.DumpMap("",items)
//			if len(items) == 2 {
//				if (items["Channel"] != nil) { 
//					switch items["Channel"].(type) {
//					case float64 :
//						channel := int(items["Channel"].(float64))
//						if (items["Timestamp"] != nil) { 
//							switch items["Timestamp"].(type) {
//							case string :
//								//Receive <- StopwatchMessage{channel,items["Timestamp"].(string)}
//								timestamp := items["Timestamp"].(string)
//								if channel == 0 {
//									// Update cell content
//									startSheet.Update(startIdx, 0, timestamp)		
//									// Make sure call Synchronize to reflect the changes
//									err = startSheet.Synchronize()
//									if err != nil {
//										log.Println("Sheet:\tError 0:",err)
//										mqttpipe.Send <- mqttpipe.Message{"stopwatch/commit",[]byte("BREAK")}
//										time.Sleep(2 * time.Second)
//										loop = false
//									} else {
//										log.Println("Sheet:\tUpdate 0:",msg)
//										startIdx = startIdx + 1	
//										mqttpipe.Send <- mqttpipe.Message{"stopwatch/commit",msg.Payload()}
//									}
//								} else if channel == 1 {
//									// Update cell content
//									finishSheet.Update(finishIdx, 0, timestamp)		
//									// Make sure call Synchronize to reflect the changes
//									err = finishSheet.Synchronize()
//									if err != nil {
//										log.Println("Sheet:\tError 0:",err)
//										mqttpipe.Send <- mqttpipe.Message{"stopwatch/commit",[]byte("BREAK")}
//										time.Sleep(2 * time.Second)
//										loop = false
//									} else {
//										log.Println("Sheet:\tUpdate 1:",msg)
//										finishIdx = finishIdx + 1
//										mqttpipe.Send <- mqttpipe.Message{"stopwatch/commit",msg.Payload()}	
//									}
//								}
//							}
//						}
//					}
//				}		
//			}
//		}
//	}
}

func checkError(err error) {
	if err != nil {
		panic(err.Error())
	}
}
