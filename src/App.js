import React,{useState} from 'react';
import AuthScreen from './screens/AuthScreen';
import AiNavigator from './navigation/AiNavigator';
import {authSession} from './services/authSession';

export default function App(){
  const [authenticated,setAuthenticated]=useState(authSession.isAuthenticated());
  if(!authenticated) return <AuthScreen onAuthenticated={()=>setAuthenticated(true)}/>;
  return <AiNavigator onLogout={()=>{authSession.clear();setAuthenticated(false)}}/>;
}
