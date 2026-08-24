import React,{useEffect,useState} from 'react';
import {SafeAreaView,ActivityIndicator} from 'react-native';
import AuthScreen from './screens/AuthScreen';
import AiNavigator from './navigation/AiNavigator';
import {authSession} from './services/authSession';

export default function App(){
  const [ready,setReady]=useState(false),[authenticated,setAuthenticated]=useState(false);
  useEffect(()=>{let mounted=true;(async()=>{try{const ok=await authSession.restore();if(mounted)setAuthenticated(ok)}finally{if(mounted)setReady(true)}})();return()=>{mounted=false}},[]);
  if(!ready) return <SafeAreaView style={{flex:1,alignItems:'center',justifyContent:'center'}}><ActivityIndicator/></SafeAreaView>;
  if(!authenticated) return <AuthScreen onAuthenticated={()=>setAuthenticated(true)}/>;
  return <AiNavigator onLogout={async()=>{await authSession.clear();setAuthenticated(false)}}/>;
}
