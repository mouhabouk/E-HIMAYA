package tn.ehimaya.keycloak.otp;

/** Sends the sign-in code by SMS. */
public interface SmsSender {

    /**
     * @param ok        the SMS provider accepted the message
     * @param simulated SIMULATION: the message went to the development gateway notify-sim
     */
    record Result(boolean ok, boolean simulated) {}

    Result send(String phone, String code, String locale);
}
