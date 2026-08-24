import React,{useEffect,useState} from 'react';
import {SafeAreaView,ActivityIndicator} from 'react-native';
import AuthScreen from './screens/AuthScreen';
import AiNavigator from './navigation/AiNavigator';
import {authSession} from './services/authSession';
import {subscribeToUpstoxRedirect} from './services/upstoxOAuthRedirect';

export default function App(){
  const [ready,setReady]=useState(false),[authenticated,setAuthenticated]=useState(false),[brokerRefresh,setBrokerRefresh]=useState(0);
  useEffect(()=>{let mounted=true;(async()=>{try{const ok=await authSession.restore();if(mounted)setAuthenticated(ok)}finally{if(mounted)setReady(true)}})();return()=>{mounted=false}},[]);
  useEffect(()=>subscribeToUpstoxRedirect(result=>{if(result?.error){return;}if(result?.code&&result?.state)setBrokerRefresh(v=>v+1)}),[]);
  if(!ready) return <SafeAreaView style={{flex:1,alignItems:'center',justifyContent:'center'}}><ActivityIndicator/></SafeAreaView>;
  if(!authenticated) return <AuthScreen onAuthenticated={()=>setAuthenticated(true)}/>;
  return <AiNavigator key={brokerRefresh} onLogout={async()=>{await authSession.clear();setAuthenticated(false)}}/>;
}
