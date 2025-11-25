"use client"
/*import { PipecatClient } from "@pipecat-ai/client-js";
import {
  PipecatClientProvider,
  PipecatClientAudio,
  usePipecatClient,
} from "@pipecat-ai/client-react";
import { DailyTransport } from "@pipecat-ai/daily-transport";
*/
import { PipecatClient } from "@pipecat-ai/client-js"
import { SmallWebRTCTransport } from "@pipecat-ai/small-webrtc-transport"
import { PipecatClientProvider, usePipecatClient, PipecatClientAudio } from "@pipecat-ai/client-react"
import {useState,useEffect} from "react"

/*const client = new PipecatClient({
  transport: new DailyTransport(),
  enableMic: true,
});*/

/*
const client = new PipecatClient({
  transport: new SmallWebRTCTransport(),
  enableMic: true,
  enableCam: false
})*/

/*
await client.connect({
  webrtcUrl: '/api/offer' // Your WebRTC signaling endpoint
})*/

export default function App() {
	const [client,setClient]=useState(null)
	
	useEffect(()=>{
		const initClient = async () => {
      		const { PipecatClient } = await import("@pipecat-ai/client-js");
	      const { SmallWebRTCTransport } = await import("@pipecat-ai/small-webrtc-transport");
	      
	      const newClient = new PipecatClient({
		transport: new SmallWebRTCTransport(),
		enableMic: true,
		enableCam: false
	      });
	      setClient(newClient);
	    };
	    initClient();	
	},[])
	

  return (
    <PipecatClientProvider client={client}>
      <VoiceBot />
      <PipecatClientAudio />
    </PipecatClientProvider>
  );
}


function VoiceBot() {
  const client = usePipecatClient();
console.log('client : ',client)
  /*const handleClick = async () => {
    await client.startBotAndConnect({
      endpoint: `${process.env.PIPECAT_API_URL || "/api"}/connect`
    });
  };*/
  
  const handleClick = async () => {
  let response
  try{
/*    response =await client.startBotAndConnect({
      endpoint: "http://localhost:7860/offer" // Returns {webrtcUrl: "/api/offer"}
	});*/
	
	response = await client.connect({webrtcUrl:'http://localhost:7860/api/offer'})
	}
	catch(e){
		console.log('ERROR : ',e)
	}
	console.log('response from startBotAndConnect : ',response)
	
	}
	

  return (
    <button onClick={handleClick}>Start Conversation</button>
  );
}
