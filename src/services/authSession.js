import {authApi} from './authApi';
let accessToken = null;
export const authSession = {
  async login(username,password){const result=await authApi.login(username,password);accessToken=result.access_token;return result;},
  async register(username,password){const result=await authApi.register(username,password);accessToken=result.access_token;return result;},
  getToken(){return accessToken;},
  isAuthenticated(){return Boolean(accessToken);},
  clear(){accessToken=null;},
};
export function withAuthHeaders(headers={}){return accessToken?{...headers,Authorization:`Bearer ${accessToken}`} : headers;}
