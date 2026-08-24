import * as Keychain from 'react-native-keychain';
const SERVICE = 'ai-trading-platform.auth';
export async function saveAccessToken(token){if(!token) throw new Error('access token is required');await Keychain.setGenericPassword('access-token',token,{service:SERVICE});}
export async function getAccessToken(){const credentials=await Keychain.getGenericPassword({service:SERVICE});return credentials?credentials.password:null;}
export async function clearAccessToken(){await Keychain.resetGenericPassword({service:SERVICE});}
