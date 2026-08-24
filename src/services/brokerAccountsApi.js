import {withAuthHeaders} from './authSession';
import {API_BASE_URL} from './marketDataApi';
async function request(path, options={}){const response=await fetch(`${API_BASE_URL}${path}`,{...options,headers:withAuthHeaders({'Content-Type':'application/json',...(options.headers||{})})});const body=await response.json().catch(()=>({}));if(!response.ok)throw new Error(body.detail||`Request failed (${response.status})`);return body;}
export const brokerAccountsApi={list:()=>request('/broker-accounts'),create:(broker,accountLabel,credentials)=>request('/broker-accounts',{method:'POST',body:JSON.stringify({broker,account_label:accountLabel,credentials})}),remove:id=>request(`/broker-accounts/${id}`,{method:'DELETE'})};
