import {authApi} from './authApi';
import {saveAccessToken,getAccessToken,clearAccessToken} from './secureTokenStorage';
let accessToken = null;
export const authSession = {
  async restore(){ accessToken=await getAccessToken(); return Boolean(accessToken); },
  async login(username,password){const result=await authApi.login(username,password);accessToken=result.access_token;await saveAccessToken(accessToken);return result;},
  async register(username,password){const result=await authApi.register(username,password);accessToken=result.access_token;await saveAccessToken(accessToken);return result;},
  getToken(){return accessToken;},
  isAuthenticated(){return Boolean(accessToken);},
  async clear(){accessToken=null;await clearAccessToken();},
};
export function withAuthHeaders(headers={}){return accessToken?{...headers,Authorization:`Bearer ${accessToken}`} : headers;}
