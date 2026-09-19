import java.security.SecureRandom;
import javax.crypto.KeyGenerator;
import javax.crypto.Cipher;
import javax.crypto.spec.GCMParameterSpec;
import javax.crypto.SecretKey;
import java.util.Base64;
public class PiaozoneVector {
 public static void main(String[] args) throws Exception {
  SecureRandom r=SecureRandom.getInstance("SHA1PRNG", "SUN");r.setSeed("synthetic-key".getBytes("UTF-8"));
  KeyGenerator kg=KeyGenerator.getInstance("AES");kg.init(128,r);SecretKey k=kg.generateKey();
  byte[] iv=new byte[12];for(int i=0;i<12;i++)iv[i]=(byte)i;
  Cipher c=Cipher.getInstance("AES/GCM/NoPadding");c.init(Cipher.ENCRYPT_MODE,k,new GCMParameterSpec(128,iv));
  byte[] e=c.doFinal("{\"amount\":0.10,\"name\":\"测试\"}".getBytes("UTF-8"));
  byte[] out=new byte[12+e.length];System.arraycopy(iv,0,out,0,12);System.arraycopy(e,0,out,12,e.length);
  System.out.println(Base64.getEncoder().encodeToString(k.getEncoded()));System.out.println(Base64.getEncoder().encodeToString(out));
 }
}
